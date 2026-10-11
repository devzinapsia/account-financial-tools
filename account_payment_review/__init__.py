from . import models
from . import wizards


def post_init_hook(env):
    """The review circuit starts with the installation: vendor payments
    confirmed before it don't require review (a reviewer can still review
    any of them on purpose). Their issuer is unknown, so fall back to
    whoever created them, which still lets the "a reviewer can't review
    their own payment" rule and the observation activities work.
    """
    env.cr.execute(
        """
        UPDATE account_payment
           SET review_state = 'not_required',
               review_issuer_id = create_uid
         WHERE review_state IS NULL
           AND state IN ('in_process', 'paid')
           AND payment_type = 'outbound'
           AND partner_type = 'supplier'
        """
    )
