---
layout: default
title: Backend wallets
nav_order: 3
---


Backend wallets
===============

LNbits can run on top of many lightning-network funding sources with more being added regularly.

A backend wallet can be configured using the following LNbits environment variables:

### CLNRest (using [runes](https://docs.corelightning.org/reference/lightning-createrune))

- `LNBITS_BACKEND_WALLET_CLASS`: **CLNRestWallet**
- `CLNREST_URL`: `https://127.0.0.1:3010`
- `CLNREST_NODEID`: `lightning-cli getinfo | jq -r .id`
- `CLNREST_READONLY_RUNE`: `lightning-cli createrune restrictions='[["method=listfunds", "method=listpays", "method=listinvoices", "method=getinfo", "method=summary", "method=waitanyinvoice"]]' | jq -r .rune`
- `CLNREST_INVOICE_RUNE`: `lightning-cli createrune restrictions='[["method=invoice"], ["pnameamount_msat<1000001"], ["pnamelabel^LNbits"], ["rate=60"]]' | jq -r .rune`
- `CLNREST_PAY_RUNE`: `lightning-cli createrune restrictions='[["method=pay"], ["pinvbolt11_amount<1001"], ["pnamelabel^LNbits"], ["rate=1"]]' | jq -r .rune`
- `CLNREST_CERT`: `/home/lightningd/.lightning/bitcoin/server.pem` (or the content of the `server.pem` file)

### CoreLightning

- `LNBITS_BACKEND_WALLET_CLASS`: **CoreLightningWallet**
- `CORELIGHTNING_RPC`: /file/path/lightning-rpc

### CoreLightning REST

- `LNBITS_BACKEND_WALLET_CLASS`: **CoreLightningRestWallet**
- `CORELIGHTNING_REST_URL`: http://127.0.0.1:8185/
- `CORELIGHTNING_REST_MACAROON`: /file/path/admin.macaroon or Base64/Hex
- `CORELIGHTNING_REST_CERT`: /home/lightning/clnrest/tls.cert

### Spark (Core Lightning)

- `LNBITS_BACKEND_WALLET_CLASS`: **SparkWallet**
- `SPARK_URL`: http://10.147.17.230:9737/rpc
- `SPARK_TOKEN`: secret_access_key

### LND (REST)

- `LNBITS_BACKEND_WALLET_CLASS`: **LndRestWallet**
- `LND_REST_ENDPOINT`: http://10.147.17.230:8080/
- `LND_REST_CERT`: /file/path/tls.cert
- `LND_REST_MACAROON`: /file/path/admin.macaroon or Base64/Hex

or

- `LND_REST_MACAROON_ENCRYPTED`: eNcRyPtEdMaCaRoOn

### LND (gRPC)

- `LNBITS_BACKEND_WALLET_CLASS`: **LndWallet**
- `LND_GRPC_ENDPOINT`: ip_address
- `LND_GRPC_PORT`: port
- `LND_GRPC_CERT`: /file/path/tls.cert
- `LND_GRPC_MACAROON`: /file/path/admin.macaroon or Base64/Hex

You can also use an AES-encrypted macaroon (more info) instead by using

- `LND_GRPC_MACAROON_ENCRYPTED`: eNcRyPtEdMaCaRoOn

To encrypt your macaroon, run `poetry run python lnbits/wallets/macaroon/macaroon.py`.

### LNbits

- `LNBITS_BACKEND_WALLET_CLASS`: **LNbitsWallet**
- `LNBITS_ENDPOINT`: e.g. https://lnbits.com
- `LNBITS_KEY`: lnbitsAdminKey

### LNPay

For the invoice listener to work you have a publicly accessible URL in your LNbits and must set up [LNPay webhooks](https://dashboard.lnpay.co/webhook/) pointing to `<your LNbits host>/wallet/webhook` with the "Wallet Receive" event and no secret. For example, `https://mylnbits/wallet/webhook` will be the Endpoint Url that gets notified about the payment.

- `LNBITS_BACKEND_WALLET_CLASS`: **LNPayWallet**
- `LNPAY_API_ENDPOINT`: https://api.lnpay.co/v1/
- `LNPAY_API_KEY`: sak_apiKey
- `LNPAY_WALLET_KEY`: waka_apiKey

### OpenNode

For the invoice to work you must have a publicly accessible URL in your LNbits. No manual webhook setting is necessary.

- `LNBITS_BACKEND_WALLET_CLASS`: **OpenNodeWallet**
- `OPENNODE_API_ENDPOINT`: https://api.opennode.com/
- `OPENNODE_KEY`: opennodeAdminApiKey

### Alby

For the invoice to work you must have a publicly accessible URL in your LNbits. No manual webhook setting is necessary. You can generate an alby access token here: https://getalby.com/developer/access_tokens/new

- `LNBITS_BACKEND_WALLET_CLASS`: **AlbyWallet**
- `ALBY_API_ENDPOINT`: https://api.getalby.com/
- `ALBY_ACCESS_TOKEN`: AlbyAccessToken

### Cliche Wallet

- `CLICHE_ENDPOINT`: ws://127.0.0.1:12000
