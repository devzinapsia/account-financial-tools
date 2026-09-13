import unittest

from odoo.addons.account_statement_reconcile_improvements.tools.ar_id_extraction import (
    _cuit_check_digit,
    extract_cuit,
    extract_dni,
    is_valid_cuit,
)


def _valid_cuit(prefix, middle):
    """Build a real, checksum-valid 11-digit CUIT for test fixtures, instead
    of hand-picking digits and hoping they happen to validate."""
    digits10 = f'{prefix}{middle}'
    assert len(digits10) == 10
    check_digit = _cuit_check_digit(digits10)
    assert check_digit is not None, "test fixture prefix/middle happens to hit the invalid modulo-11=10 case, change it"
    return f'{digits10}{check_digit}'


class TestArIdExtraction(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.valid_cuit = _valid_cuit('20', '12345678')

    def _dashed(self, cuit):
        return f'{cuit[:2]}-{cuit[2:10]}-{cuit[10]}'

    def test_valid_cuit_with_dashes(self):
        text = self._dashed(self.valid_cuit)
        self.assertEqual(extract_cuit(text), self.valid_cuit)

    def test_valid_cuit_without_dashes(self):
        self.assertEqual(extract_cuit(self.valid_cuit), self.valid_cuit)

    def test_valid_cuit_with_spaces(self):
        text = f'{self.valid_cuit[:2]} {self.valid_cuit[2:10]} {self.valid_cuit[10]}'
        self.assertEqual(extract_cuit(text), self.valid_cuit)

    def test_valid_cuit_embedded_in_text(self):
        text = f'PAGO CUIT {self._dashed(self.valid_cuit)} FACT 123'
        self.assertEqual(extract_cuit(text), self.valid_cuit)

    def test_two_cuits_in_same_legend_leaves_blank(self):
        other_cuit = _valid_cuit('30', '71243964')
        text = f'{self._dashed(self.valid_cuit)} y tambien {self._dashed(other_cuit)}'
        self.assertIsNone(extract_cuit(text))

    def test_invalid_check_digit_is_not_taken_as_valid(self):
        bad_digit = (int(self.valid_cuit[10]) + 1) % 10
        bad_cuit = f'{self.valid_cuit[:10]}{bad_digit}'
        self.assertFalse(is_valid_cuit(bad_cuit))
        self.assertIsNone(extract_cuit(bad_cuit))

    def test_no_cuit_in_text(self):
        self.assertIsNone(extract_cuit('Transferencia varios conceptos'))

    def test_cuit_substring_of_longer_account_number_is_not_matched(self):
        # An 18-digit CBU must never be mistaken for an embedded 11-digit CUIT.
        cbu = '005292225001030021' + '000'  # pad to make sure no 11-digit window is isolated
        self.assertIsNone(extract_cuit(f'Transf.Inmediata e/Ctas.Dist Tit.O/Bco VAR Cta:{cbu}'))

    def test_modulo_11_remainder_10_is_invalid(self):
        # Find a 10-digit prefix whose modulo-11 remainder is exactly 10 (no valid check digit exists).
        found = None
        for middle in range(10 ** 8):
            digits10 = f'20{middle:08d}'
            if _cuit_check_digit(digits10) is None:
                found = digits10
                break
        self.assertIsNotNone(found, "could not find a remainder=10 fixture, algorithm may have changed")
        for check_digit in range(10):
            self.assertFalse(is_valid_cuit(f'{found}{check_digit}'))

    # --- DNI (best-effort) ---

    def test_dni_with_dni_prefix(self):
        self.assertEqual(extract_dni('Transferencia DNI 30123456 varios'), '30123456')

    def test_dni_with_thousand_separators(self):
        self.assertEqual(extract_dni('Pago DNI 30.123.456 alquiler'), '30123456')

    def test_dni_bare_number_unambiguous(self):
        self.assertEqual(extract_dni('Varios 1234567 transferencia'), '1234567')

    def test_dni_does_not_overlap_a_cuit(self):
        # The CUIT's own middle digits look like a DNI-shaped number; must not be picked up separately.
        text = self._dashed(self.valid_cuit)
        self.assertIsNone(extract_dni(text))

    def test_dni_no_candidate(self):
        self.assertIsNone(extract_dni('Transferencia varios conceptos'))

    def test_dni_ambiguous_multiple_candidates(self):
        self.assertIsNone(extract_dni('Ref 1234567 y tambien 7654321'))

    # --- Real bank export legends (RESUMEN BBVA / RESUMEN CREDICOOP samples) ---

    def test_real_bbva_legend_extracts_cuit(self):
        text = 'MOTOROLA SOLUTIO00000000000804396012    1826024ND35     CUIT 30662053534'
        self.assertEqual(extract_cuit(text), '30662053534')

    def test_real_bbva_legend_dni_false_positive_is_a_known_limitation(self):
        # "1826024" here is an internal reference code, not a real DNI - this
        # documents the best-effort DNI heuristic's known false-positive risk
        # (see README "Decisiones de diseño").
        text = 'MOTOROLA SOLUTIO00000000000804396012    1826024ND35     CUIT 30662053534'
        self.assertEqual(extract_dni(text), '1826024')

    def test_real_credicoop_legend_extracts_cuit(self):
        text = 'Transf. Interbanking - Distinto Titular Ord.:30712439641-SINDELARS SRL'
        self.assertEqual(extract_cuit(text), '30712439641')

    def test_real_credicoop_cbu_legend_has_no_cuit_or_dni(self):
        text = 'Transf.Inmediata e/Ctas.Dist Tit.O/Bco VAR Cta:005292225001030021'
        self.assertIsNone(extract_cuit(text))
        self.assertIsNone(extract_dni(text))


if __name__ == '__main__':
    unittest.main()
