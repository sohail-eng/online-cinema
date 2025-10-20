class CommentNotFoundError(Exception):
    pass

class MovieNotFoundError(Exception):
    pass

class UserDontHavePermissionError(Exception):
    pass

class SomethingWentWrongError(Exception):
    pass

class MovieAlreadyIsPurchasedOrInCartError(Exception):
    pass

class CartNotExistError(Exception):
    pass

class OrderDoesNotExistError(Exception):
    pass

class PaymentNotFoundError(Exception):
    pass