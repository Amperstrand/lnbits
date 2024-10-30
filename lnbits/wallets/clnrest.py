import asyncio
import json
import random
from typing import AsyncGenerator, Dict, Optional

import httpx
import ssl
import os
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

import base64
import uuid
#from pathlib import Path


#delete this
#from .base import (
#    InvoiceResponse,
#    PaymentPendingStatus,
#    PaymentResponse,
#    PaymentStatus,
#    StatusResponse,
#    Wallet,
#)
#from .macaroon import load_macaroon


class CLNRestWallet(Wallet):
    def __init__(self):

        if not settings.clnrest_url:
            raise ValueError("Cannot initialize CLNRestWallet: missing CLNREST_URL")

        if not settings.clnrest_nodeid:
            raise ValueError("Cannot initialize CLNRestWallet: missing CLNREST_NODEID")

        if settings.clnrest_url.startswith("https://"):
            logger.info("Using SSL for CLNRestWallet connection.")
            logger.info(settings.clnrest_cert)
            if not settings.clnrest_cert:
                logger.warning(
                        "No certificate provided for CLNRestWallet. "
                        "This setup requires a publicly issued certificate or self-signed certificate trust settings. "
                        "Set CLNREST_CERT to the certificate file path or the conents of the cert."
                    )
        elif any(settings.clnrest_url.startswith(prefix) for prefix in ["http://localhost", "http://127.0.0.1", "http://[::1]"]):
            logger.warning("Not using SSL for connection to CLNRestWallet")
        elif (settings.clnrest_url.startswith("http://")):
            raise ValueError(
                "Insecure HTTP connections are only allowed for localhost or equivalent IP addresses. "
                "Set CLNREST_URL to https:// for external connections or use localhost."
            )

        if settings.clnrest_readonly_rune:
            self.readonly_rune=settings.clnrest_readonly_rune
            logger.debug(f"TODO: make sure that it has the correct permissions: {self.readonly_rune}:")
            logger.debug(self.readonly_rune)
            #logger.debug(json.dumps(self.readonly_rune.to_dict()))


        else:
            raise ValueError(
                "Cannot initialize CLNRestWallet: missing CLNREST_READONLY_RUNE. Create one with:\n"
                """ lightning-cli createrune restrictions='[["method=listfunds", "method=listpays", "method=listinvoices", "method=getinfo", "method=summary", "method=waitanyinvoice"]]' """
            )

        if settings.clnrest_invoice_rune:
            self.invoice_endpoint = "v1/invoice"
            logger.debug(f"TODO: decode this invoice_rune and make sure that it has the correct permissions: {settings.clnrest_invoice_rune}:")
            self.invoice_rune=settings.clnrest_invoice_rune
            logger.debug(self.invoice_rune)
            #logger.debug(json.dumps(self.invoice_rune.to_dict()))
        else:
            self.invoice_endpoint = None
            self.invoice_rune=None
            logger.warning(
                "Will be unable to create any invoices without setting 'CLNREST_INVOICE_RUNE'. Please create one with one of the following commands:\n"
                """ lightning-cli createrune restrictions='[["method=invoice"], ["pnameamount_msat<1000001"], ["pname_label^LNbits"], ["rate=60"]]' """
                )


        if settings.clnrest_pay_rune:
            self.pay_endpoint = "v1/pay"
            logger.debug(f"TODO: decode this pay_rune and make sure that it has the correct permissions: {settings.clnrest_pay_rune}:")
            self.pay_rune = settings.clnrest_pay_rune
            logger.debug(self.pay_rune)
            # logger.debug(json.dumps(self.pay_rune.to_dict()))
        else:
            self.pay_endpoint = None
            self.pay_rune = None
            logger.warning(
                "Will be unable to make any payments without setting 'CLNREST_PAY_RUNE'. Please create one with one of the following commands:\n"
                """ lightning-cli createrune restrictions='[["method=pay"], ["pnameamount_msat<1000001"], ["rate=60"]]' """
            )

        self.url = settings.clnrest_url[:-1] if settings.clnrest_url.endswith("/") else settings.clnrest_url

        self.base_headers = {
            "accept": "application/json",
            "User-Agent": settings.user_agent,
            "Content-Type": "application/json",
        }
        self.readonly_headers = {**self.base_headers, "rune": settings.clnrest_readonly_rune, "nodeid": settings.clnrest_nodeid}
        self.pay_headers = {**self.base_headers, "rune": settings.clnrest_pay_rune, "nodeid": settings.clnrest_nodeid}


        self.cert = settings.clnrest_cert or False
        #self.client = httpx.AsyncClient(verify=self.cert, headers=headers)
        self.client = self.create_client()

        self.last_pay_index = 0
        self.statuses = {
            "paid": True,
            "complete": True,
            "failed": False,
            "pending": None,
        }

    def create_client(self) -> httpx.AsyncClient:
        """Create an HTTP client with specified headers and SSL configuration."""

        if self.cert:
            ssl_context = ssl.create_default_context()

            # Check if `self.cert` is a file path or a PEM string
            if os.path.isfile(self.cert):
                ssl_context.load_verify_locations(self.cert)
            else:
                # Assume `self.cert` is a PEM-encoded string and load with cadata
                ssl_context.load_verify_locations(cadata=self.cert)

            #Ignore the certificate authority and hostname since we are using a hardcoded selfsigned cert
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            return httpx.AsyncClient(base_url=self.url, verify=ssl_context)
        else:
            #todo: this assertion is redundant. should it be done here or in init?
            if not any(self.url.startswith(prefix) for prefix in ["http://localhost", "http://127.0.0.1", "http://[::1]"]):
                raise ValueError(
                    "Insecure HTTP connections are only allowed for localhost or equivalent IP addresses. "
                    "Set CLNREST_URL to https:// for external connections or use localhost."
                )
            return httpx.AsyncClient(base_url=self.url, verify=False)

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as e:
            logger.warning(f"Error closing wallet connection: {e}")

    async def status(self) -> StatusResponse:
        try:
            logger.debug("REQUEST to /v1/listfunds")
            r = await self.client.post( "/v1/listfunds", timeout=15, headers=self.readonly_headers)

        except httpx.ReadTimeout:
            logger.error("Timeout error: The server did not respond in time. This also happens if the server is running https and you are trying to connect with http.")
            return StatusResponse(f"Unable to connect to 'v1/listfunds'", 0)

        except (httpx.ConnectError, httpx.RequestError) as e:
            logger.error(f"Connection error: {str(e)}")
            return StatusResponse(f"Unable to connect to 'v1/listfunds'", 0)

        try:
            response_data = r.json()
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            return StatusResponse(f"Failed to decode JSON response from {self.url}", 0)

        if r.is_error or "error" in response_data:
            error_message = response_data.get("error", r.text)
            return StatusResponse(f"Failed to connect to {self.url}, got: '{error_message}'...", 0)

        if not response_data:
            return StatusResponse("no data", 0)

        channels = response_data.get("channels")
        if channels is None:
            total_our_amount_msat = 0
        else:
            total_our_amount_msat = sum(channel["our_amount_msat"] for channel in channels)

        return StatusResponse(None, total_our_amount_msat)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        label_prefix: Optional[str] = "LNbits ",
        **kwargs,
    ) -> InvoiceResponse:

        if not self.invoice_rune:
            return InvoiceResponse( False, None, None, "Unable to invoice without an invoice rune")
        else:
            self.invoice_headers = {**self.base_headers, "rune": self.invoice_rune, "nodeid": settings.clnrest_nodeid}

        #TODO: the identifier could be used to encode the LNBits user or the LNBits wallet that is creating the invoice
        identifier = "todoWalletIdGoesHere"
        label = label_prefix + identifier + ' ' + base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b'=').decode('utf-8')

        data: Dict = {
            "amount_msat": amount * 1000,
            "description": memo,
            "label": label,
        }
        if description_hash and not unhashed_description:
            raise Unsupported(
                "'description_hash' unsupported by CoreLightningRest, todo: find out if this is still the case with the new clnrest"
                "provide 'unhashed_description'"
            )

        if unhashed_description:
            data["description"] = unhashed_description.decode("utf-8")

        if kwargs.get("expiry"):
            data["expiry"] = kwargs["expiry"]

        if kwargs.get("preimage"):
            data["preimage"] = kwargs["preimage"]

        logger.debug(f"REQUEST to {self.invoice_endpoint}: : {json.dumps(data)}")

        logger.debug(f"REQUEST to {self.invoice_endpoint}: {json.dumps(data)}")

        try:
            r = await self.client.post(
                self.invoice_endpoint,
                json=data,
                headers=self.invoice_headers,
            )
            r.raise_for_status()
            response_data = r.json()

            if "error" in response_data:
                return InvoiceResponse(False, None, None, f"Server error: '{response_data['error']}'")

            if "payment_hash" not in response_data or "bolt11" not in response_data:
                return InvoiceResponse(False, None, None, "Server error: 'missing required fields'")

            return InvoiceResponse(True, response_data["payment_hash"], response_data["bolt11"], None)

        except json.JSONDecodeError:
            return InvoiceResponse(False, None, None, "Server error: 'invalid json response'")
        except Exception as exc:
            logger.warning(f"Unable to connect to {self.url}: {exc}")
            return InvoiceResponse(False, None, None, f"Unable to connect to {self.url}.")


    async def pay_invoice(
            self,
            bolt11: str,
            fee_limit_msat: int,
            label_prefix: Optional[str] = "LNbits ",
            ) -> PaymentResponse:
        #todo: rune restrictions will not be enforced for internal payments within the lnbits instance as they are not routed through to core lightning
        #this should be a configurable option but maybe part of a seperate pull request

        if not self.pay_headers:
            return InvoiceResponse( False, None, None, "Unable to invoice without a valid rune")

        try:
            invoice = decode(bolt11)
        except Bolt11Exception as exc:
            return PaymentResponse(False, None, None, None, str(exc))

        if not invoice.amount_msat or invoice.amount_msat <= 0:
            error_message = "0 amount invoices are not allowed"
            return PaymentResponse(False, None, None, None, error_message)

        identifier = "todoWalletIdGoesHere"
        label = label_prefix + identifier + ' ' + base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b'=').decode('utf-8')

        if (self.pay_endpoint == "v1/pay"):
            fee_limit_percent = fee_limit_msat / invoice.amount_msat * 100
            data = {
                "bolt11": bolt11,
                "label": label,
                "description": invoice.description,
                "maxfeepercent": f"{fee_limit_percent}",
                "exemptfee": 0,  # so fee_limit_percent is applied even on payments
                # with fee < 5000 millisatoshi (which is default value of exemptfee)
            }

        logger.debug(f"REQUEST to {self.pay_endpoint}: {json.dumps(data)}")
        try:
            r = await self.client.post(
                self.pay_endpoint,
                json=data,
                headers=self.pay_headers,
                timeout=None,
            )

            r.raise_for_status()
            data = r.json()

            status = self.statuses.get(data["status"])
            if "payment_preimage" not in data:
                return PaymentResponse(
                    status,
                    None,
                    None,
                    None,
                    data.get("error"),
                )

            checking_id = data["payment_hash"]
            preimage = data["payment_preimage"]
            fee_msat = data["msatoshi_sent"] - data["msatoshi"]

            return PaymentResponse(status, checking_id, fee_msat, preimage, None)
        except httpx.HTTPStatusError as exc:
            try:
                logger.debug(exc)
                data = exc.response.json()
                error_code = int(data["error"]["code"])
                if error_code in self.pay_failure_error_codes:
                    error_message = f"Payment failed: {data['error']['message']}"
                    return PaymentResponse(False, None, None, None, error_message)
                error_message = f"REST failed with {data['error']['message']}."
                return PaymentResponse(None, None, None, None, error_message)
            except Exception as exc:
                error_message = f"Unable to connect to {self.url}."
                return PaymentResponse(None, None, None, None, error_message)

        except json.JSONDecodeError:
            return PaymentResponse(
                None, None, None, None, "Server error: 'invalid json response'"
            )
        except KeyError as exc:
            logger.warning(exc)
            return PaymentResponse(
                None, None, None, None, "Server error: 'missing required fields'"
            )
        except Exception as exc:
            logger.info(f"Failed to pay invoice {bolt11}")
            logger.warning(exc)
            return PaymentResponse(
                None, None, None, None, f"Unable to connect to {self.url}."
            )


    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        data: Dict = { "payment_hash": checking_id }
        logger.debug(f"REQUEST to /v1/listinvoices: {json.dumps(data)}")
        r = await self.client.post(
            "/v1/listinvoices",
            json=data,
            headers=self.readonly_headers,
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
            return PaymentPendingStatus()


    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        data: Dict = { "payment_hash": checking_id }

        logger.debug(f"REQUEST to /v1/listpays: {json.dumps(data)}")
        r = await self.client.post(
            "/v1/listpays",
            json=data,
            headers=self.readonly_headers,
        )
        try:
            r.raise_for_status()
            data = r.json()
            logger.debug(data)

            if r.is_error or "error" in data:
                logger.error(f"API response error: {data}")
                raise Exception("Error in corelightning-rest response")

            pays_list = data.get("pays", [])
            if not pays_list:
                logger.debug(f"No payments found for payment hash {checking_id}. Payment is pending.")
                return PaymentStatus(self.statuses.get("pending"))

            if len(pays_list) != 1:
                error_message = f"Expected one payment status, but found {len(pays_list)}"
                logger.error(error_message)
                raise Exception(error_message)

            pay = pays_list[0]
            logger.debug(f"Payment status from API: {pay['status']}")

            fee_msat, preimage = None, None
            if pay['status'] == 'complete':
                fee_msat = pay["amount_sent_msat"] - pay["amount_msat"]
                preimage = pay["preimage"]

            return PaymentStatus(self.statuses.get(pay["status"]), fee_msat, preimage)
        except Exception as e:
            logger.error(f"Error getting payment status: {e}")
            return PaymentStatus(None)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while True:
            try:
                waitanyinvoice_timeout=None
                request_timeout = httpx.Timeout(connect=5.0, read=waitanyinvoice_timeout, write=60.0, pool=60.0)
                data: Dict = { "lastpay_index": self.last_pay_index, "timeout": waitanyinvoice_timeout}
                url = "/v1/waitanyinvoice"
                logger.debug(f"REQUEST(stream) to  /v1/waitanyinvoice with data: {data}.")
                async with self.client.stream("POST", url, json=data, headers=self.readonly_headers,  timeout=request_timeout) as r:
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
                        logger.trace('end')

                        # hack to return payment_hash if the above shouldn't work
                        # TODO: explain why this would ever happen. Maybe if the rune doesn't have permission to list any invoices
                        # the code is copied from corelightningrest.py, I just don't see when it needs to run, so I commented it out
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
                        #yield paid_invoice["invoices"][0]["payment_hash"]

            except Exception as exc:
                logger.debug(
                    f"lost connection to corelightning-rest invoices stream: '{exc}', "
                    "reconnecting..."
                )
                await asyncio.sleep(0.02)
