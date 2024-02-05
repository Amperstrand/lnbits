import asyncio
import json
import random
from typing import AsyncGenerator, Dict, Optional

import httpx
from bolt11 import Bolt11Exception
from bolt11.decode import decode
from loguru import logger

from lnbits.settings import settings

from .base import (
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    Unsupported,
    Wallet,
)

def parse_msat(value):
    # Check if the value ends with 'msat' and remove it
    if value.endswith("msat"):
        return int(value[:-4])  # Remove the last 4 characters ('msat') and convert to int
    else:
        raise ValueError(f"Unexpected format for amount: {value}")

class CLNRestWallet(Wallet):

    def __init__(self):
        if not settings.clnrest_url:
            raise ValueError(
                "cannot initialize CLNRest: "
                "missing clnrest_url"
            )
        if not settings.clnrest_rune:
            raise ValueError(
                "cannot initialize CLNRest: "
                "missing clnrest_rune"
            )
        rune = settings.clnrest_rune
        nodeid = settings.clnrest_nodeid

        if not rune:
            raise ValueError(
                "cannot initialize CLNRest: "
                "invalid clnrest_rune provided"
            )

        self.url = self.normalize_endpoint(settings.clnrest_url)

        headers = {
            "accept": "application/json",
            "User-Agent": settings.user_agent,
            "Content-Type": "application/json",
            "rune": rune,
            "nodeid": nodeid,
        }

        self.cert = settings.clnrest_cert or False
        self.client = httpx.AsyncClient(verify=self.cert, headers=headers)
        self.last_pay_index = 0
        self.statuses = {
            "paid": True,
            "complete": True,
            "failed": False,
            "pending": None,
        }

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as e:
            logger.warning(f"Error closing wallet connection: {e}")

    async def status(self) -> StatusResponse:
        data={}
        logger.debug(f"REQUEST to /v1/getinfo: {json.dumps(data)}")
        r = await self.client.post( f"{self.url}/v1/listfunds", timeout=5, json=data)
        r.raise_for_status()
        if r.is_error or "error" in r.json():
            try:
                data = r.json()
                error_message = data["error"]
            except Exception:
                error_message = r.text
            return StatusResponse(
                f"Failed to connect to {self.url}, got: '{error_message}...'", 0
            )

        data = r.json()
        if len(data) == 0:
            return StatusResponse("no data", 0)

        if not data.get("channels"):
            return StatusResponse("no data or no channels available", 0)

        total_our_amount_msat = sum(parse_msat(channel["our_amount_msat"]) for channel in data["channels"])

        #todo: calculate the amount of spendable sats based on rune permissions or some sort of accounting system?

        return StatusResponse(None, total_our_amount_msat)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        **kwargs,
    ) -> InvoiceResponse:
        label = f"lbl{random.random()}"
        data: Dict = {
            "amount_msat": amount * 1000,
            "description": memo,
            "label": label,
        }
        if description_hash and not unhashed_description:
            raise Unsupported(
                "'description_hash' unsupported by CoreLightningRest, "
                "provide 'unhashed_description'"
            )

        if unhashed_description:
            data["description"] = unhashed_description.decode("utf-8")

        if kwargs.get("expiry"):
            data["expiry"] = kwargs["expiry"]

        if kwargs.get("preimage"):
            data["preimage"] = kwargs["preimage"]

        logger.debug(f"REQUEST to /v1/invoice: : {json.dumps(data)}")
        r = await self.client.post(
            f"{self.url}/v1/invoice",
            json=data,
        )

        if r.is_error or "error" in r.json():
            try:
                data = r.json()
                error_message = data["error"]
            except Exception:
                error_message = r.text

            return InvoiceResponse(False, None, None, error_message)

        data = r.json()
        assert "payment_hash" in data
        assert "bolt11" in data
        return InvoiceResponse(True, data["payment_hash"], data["bolt11"], None)

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        try:
            invoice = decode(bolt11)
        except Bolt11Exception as exc:
            return PaymentResponse(False, None, None, None, str(exc))

        if not invoice.amount_msat or invoice.amount_msat <= 0:
            error_message = "0 amount invoices are not allowed"
            return PaymentResponse(False, None, None, None, error_message)

        if settings.clnrest_enable_renepay:
            api_endpoint = f"{self.url}/v1/renepay"
            maxfee = fee_limit_msat
            maxdelay = 300
            data = {
                "invstring": bolt11,
                "maxfee": maxfee,
                "retry_for": 60,
            }
                #"amount_msat": invoice.amount_msat,
                #"maxdelay": maxdelay,
                #"description": memo,
                #"label": label,
                # Add other necessary parameters like retry_for, description, label as required
        else:
            api_endpoint = f"{self.url}/v1/pay"
            fee_limit_percent = fee_limit_msat / invoice.amount_msat * 100
            data = {
                "bolt11": bolt11,
                "maxfeepercent": f"{fee_limit_percent:.11}",
                "exemptfee": 0,  # so fee_limit_percent is applied even on payments
                # with fee < 5000 millisatoshi (which is default value of exemptfee)
            }

        logger.debug(f"REQUEST to {api_endpoint}: {json.dumps(data)}")

        r = await self.client.post(
            api_endpoint,
            json=data,
            timeout=None,
        )

        if r.is_error or "error" in r.json():
            try:
                data = r.json()
                logger.debug(f"RESPONSE with error: {data}")
                error_message = data["error"]
            except Exception:
                error_message = r.text
            return PaymentResponse(False, None, None, None, error_message)

        data = r.json()
        logger.debug(f"RESPONSE: {data}")

        if data["status"] != "complete":
            return PaymentResponse(False, None, None, None, "payment failed")

        #destination = data['destination']
        #created_at = data['created_at']
        #parts = data['parts']
        status = data['status']

        checking_id = data["payment_hash"]
        preimage = data["payment_preimage"]

        amount_sent_msat_int = parse_msat(data.get('amount_sent_msat'))
        amount_msat_int = parse_msat(data.get('amount_msat'))
        fee_msat = amount_sent_msat_int - amount_msat_int

        return PaymentResponse(
            self.statuses.get(data["status"]), checking_id, fee_msat, preimage, None
        )

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        data: Dict = { "payment_hash": checking_id }
        logger.debug(f"REQUEST to /v1/listinvoices: {json.dumps(data)}")
        r = await self.client.post(
            f"{self.url}/v1/listinvoices",
            json=data,
        )
        try:
            r.raise_for_status()
            data = r.json()

            if r.is_error or "error" in data or data.get("invoices") is None:
                raise Exception("error in cln response")
            logger.debug(f"RESPONSE: invoice with payment_hash {data['invoices'][0]['payment_hash']} has status {data['invoices'][0]['status']}")
            return PaymentStatus(self.statuses.get(data["invoices"][0]["status"]))
        except Exception as e:
            logger.error(f"Error getting invoice status: {e}")
            return PaymentStatus(None)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        data: Dict = { "payment_hash": checking_id }

        logger.debug(f"REQUEST to /v1/listpays: {json.dumps(data)}")
        r = await self.client.post(
            f"{self.url}/v1/listpays",
            json=data,
        )
        try:
            r.raise_for_status()
            data = r.json()

            if r.is_error or "error" in data or not data.get("pays"):
                logger.error(f"RESPONSE with error: {data}")
                raise Exception("error in corelightning-rest response")

            pay = data["pays"][0]

            fee_msat, preimage = None, None
            if self.statuses[pay["status"]]:
                # cut off "msat" and convert to int
                fee_msat = -int(pay["amount_sent_msat"][:-4]) - int(
                    pay["amount_msat"][:-4]
                )
                preimage = pay["preimage"]

            return PaymentStatus(self.statuses.get(pay["status"]), fee_msat, preimage)
        except Exception as e:
            logger.error(f"Error getting payment status: {e}")
            return PaymentStatus(None)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while True:
            try:
                read_timeout=None
                data: Dict = { "lastpay_index": self.last_pay_index, "timeout": read_timeout}
                request_timeout = httpx.Timeout(connect=5.0, read=read_timeout, write=60.0, pool=60.0)
                url = f"{self.url}/v1/waitanyinvoice"
                logger.debug(f"REQUEST(stream) to  /v1/waitanyinvoice with data: {data}.")
                async with self.client.stream("POST", url, json=data, timeout=request_timeout) as r:
                    async for line in r.aiter_lines():
                        inv = json.loads(line)
                        if "error" in inv and "message" in inv["error"]:
                            logger.error("Error in paid_invoices_stream:", inv)
                            raise Exception(inv["error"]["message"])
                        try:
                            paid = inv["status"] == "paid"
                            self.last_pay_index = inv["pay_index"]
                            if not paid:
                                continue
                        except Exception:
                            continue
                        logger.trace(f"paid invoice: {inv}")

                        # NOTE: use payment_hash when corelightning-rest returns it
                        # when using waitAnyInvoice
                        payment_hash = inv["payment_hash"]
                        yield payment_hash

                        # hack to return payment_hash if the above shouldn't work
                        #r = await self.client.get(
                        #    f"{self.url}/v1/invoice/listInvoices",
                        #    params={"label": inv["label"]},
                        #)
                        #paid_invoice = r.json()
                        #logger.trace(f"paid invoice: {paid_invoice}")
                        #assert self.statuses[
                        #    paid_invoice["invoices"][0]["status"]
                        #], "streamed invoice not paid"
                        #assert "invoices" in paid_invoice, "no invoices in response"
                        #assert len(paid_invoice["invoices"]), "no invoices in response"
                        #logger.debug(inv)
                        #yield paid_invoice["invoices"][0]["payment_hash"]

            except Exception as exc:
                logger.debug(
                    f"lost connection to corelightning-rest invoices stream: '{exc}', "
                    "reconnecting..."
                )
                await asyncio.sleep(0.02)
