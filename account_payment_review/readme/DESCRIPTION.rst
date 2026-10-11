Internal control over vendor payments **after** they are confirmed. A
reviewer (typically one of the company's partners) goes through confirmed
vendor payments -- usually in batches, e.g. at month end -- and either signs
each one off as reviewed or records observations on it. The user who issued
the payment is notified of the observations, answers them, and the payment
goes back to the reviewer.

The review is a parallel control layer: it never blocks, resets or
modifies the payment itself, its journal entry or its reconciliation. It
only adds a review status, who reviewed it and when, the comments, and a
signed message in the chatter.

Review statuses:

* **Pending review**: confirmed after the circuit was enabled, waiting for
  the reviewer.
* **Reviewed**: signed off by the reviewer.
* **With observations**: the reviewer left a comment the issuer must
  answer.
* **Answered**: the issuer answered the observations; back to the
  reviewer.
* **Not required**: confirmed before the module was installed, matching an
  exemption, or explicitly marked so by the reviewer.

Customer payments are not part of the circuit.
