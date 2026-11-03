"""Domain failures. HTTP and legacy facades choose their own translation."""


class TransactionAccessDenied(Exception):
    code = 'transaction_read_denied'


class TransactionNotFound(Exception):
    code = 'transaction_resource_not_found'


class TradeRejected(Exception):
    code = 'trade_rejected'
