import ast
import logging

_logger = logging.getLogger(__name__)

# Context key read by account_translation_improvements' payment items list
# to show "Collect" instead of "Pay".
CONTEXT_KEY = "collect_payment_items"

# account_ux actions that open the payment items list on receivables only.
COLLECT_ACTIONS = ("account_ux.action_account_moves_customers_ledger",)


def set_collect_context_key(env, enabled):
    """Add (or remove) CONTEXT_KEY in the context of COLLECT_ACTIONS,
    keeping every other key the action already has, whatever account_ux
    puts there."""
    for xmlid in COLLECT_ACTIONS:
        action = env.ref(xmlid, raise_if_not_found=False)
        if not action:
            continue
        try:
            context = ast.literal_eval(action.context or "{}")
        except (ValueError, SyntaxError):
            # Not a plain dict literal (e.g. uses uid/active_id): leave it alone
            _logger.warning("Context of %s is not a literal dict, %s not changed", xmlid, CONTEXT_KEY)
            continue
        if enabled:
            context[CONTEXT_KEY] = True
        else:
            context.pop(CONTEXT_KEY, None)
        action.context = repr(context)


def uninstall_hook(env):
    """Leave account_ux's actions as account_ux defines them."""
    set_collect_context_key(env, False)
