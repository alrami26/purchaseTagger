import unittest

from purchase_extractor import extract_purchases


class PurchaseExtractorParsingTest(unittest.TestCase):
    def test_parses_standard_transaction_line_with_id(self):
        text = """
Purchases Made
123456 12-ENE-25 SUPERMERCADO XYZ CRC 1,234.56
Interest Charges
"""

        self.assertEqual(
            extract_purchases(text),
            [("12-ENE-25", "SUPERMERCADO XYZ", "1234.56", "CRC")],
        )

    def test_parses_transaction_line_without_id(self):
        text = """
Purchases Made
15-FEB-25 UBER TRIP USD 20.00
Interest Charges
"""

        self.assertEqual(
            extract_purchases(text),
            [("15-FEB-25", "UBER TRIP", "20.00", "USD")],
        )

    def test_normalizes_one_digit_day_to_two_digits(self):
        text = """
Purchases Made
7-MAR-25 CAFE LOCAL CRC 500.00
Interest Charges
"""

        self.assertEqual(
            extract_purchases(text),
            [("07-MAR-25", "CAFE LOCAL", "500.00", "CRC")],
        )

    def test_preserves_multiple_currencies(self):
        text = """
Purchases Made
111 01-ABR-25 TIENDA UNO CRC 1,000.00
222 02-ABR-25 HOTEL USD 80.25
333 03-ABR-25 MUSEO EUR 12.50
Interest Charges
"""

        self.assertEqual(
            extract_purchases(text),
            [
                ("01-ABR-25", "TIENDA UNO", "1000.00", "CRC"),
                ("02-ABR-25", "HOTEL", "80.25", "USD"),
                ("03-ABR-25", "MUSEO", "12.50", "EUR"),
            ],
        )

    def test_ignores_valid_looking_lines_outside_purchase_section(self):
        text = """
999 01-ENE-25 BEFORE SECTION USD 10.00
Purchases Made
123 02-ENE-25 INSIDE SECTION CRC 20.00
Interest Charges
888 03-ENE-25 AFTER SECTION EUR 30.00
"""

        self.assertEqual(
            extract_purchases(text),
            [("02-ENE-25", "INSIDE SECTION", "20.00", "CRC")],
        )

    def test_ignores_malformed_lines(self):
        text = """
Purchases Made
123 04-MAY-25 VALID LINE USD 40.00
124 05-MAY-25 MISSING AMOUNT USD
125 32-MAY-25 INVALID DAY USD 50.00
126 06-MAY-25 INVALID AMOUNT USD 50
127 07-MAY-25 INVALID CURRENCY US 60.00
not a purchase at all
Interest Charges
"""

        self.assertEqual(
            extract_purchases(text),
            [("04-MAY-25", "VALID LINE", "40.00", "USD")],
        )

    def test_parses_spanish_purchase_section_names(self):
        text = """
Resumen
Compras Realizadas
123 08-JUN-25 LIBRERIA CENTRAL CRC 9,999.00
Cargos por Intereses
999 09-JUN-25 OUTSIDE SECTION USD 10.00
"""

        self.assertEqual(
            extract_purchases(text),
            [("08-JUN-25", "LIBRERIA CENTRAL", "9999.00", "CRC")],
        )

    def test_ignores_summary_compras_text_before_bac_purchase_table(self):
        text = """
Detalle pago mínimo Pago de contado
Pago interés del periodo 24,130.85 0.10 Saldo del principal adeudado (compras) 875,055.38 38.94
Pago intereses moratorios 0.00 0.00
B) Detalle de compras del periodo
N. Referencia Fecha de pago Concepto/Descripción Lugar Moneda Monto en
colones
Monto en
dólares
************4584 ALBIN
121524873885 15-DIC-24 TURRUCARES SHOP CRC 16,000.00
011499100801 13-ENE-25 SHEIN.COM 000 0000000 _USA USD 38.94
C) Detalle de intereses
Monto por intereses corrientes 0.00 0.00
"""

        self.assertEqual(
            extract_purchases(text),
            [
                ("15-DIC-24", "TURRUCARES SHOP", "16000.00", "CRC"),
                ("13-ENE-25", "SHEIN.COM 000 0000000 _USA", "38.94", "USD"),
            ],
        )

    def test_parses_transactions_when_section_headers_are_missing(self):
        text = """
Account Summary
123 10-JUL-25 FARMACIA LOCAL CRC 12.75
Other text
"""

        self.assertEqual(
            extract_purchases(text),
            [("10-JUL-25", "FARMACIA LOCAL", "12.75", "CRC")],
        )

    def test_parses_negative_refund_amounts(self):
        text = """
Purchases Made
123 11-AGO-25 REFUND MERCHANT USD -20.00
Interest Charges
"""

        self.assertEqual(
            extract_purchases(text),
            [("11-AGO-25", "REFUND MERCHANT", "-20.00", "USD")],
        )

    def test_normalizes_lowercase_and_mixed_case_month_text(self):
        text = """
Purchases Made
123 1-sep-25 LOWER MONTH USD 1.00
124 2-Oct-25 MIXED MONTH CRC 2.00
Interest Charges
"""

        self.assertEqual(
            extract_purchases(text),
            [
                ("01-SEP-25", "LOWER MONTH", "1.00", "USD"),
                ("02-OCT-25", "MIXED MONTH", "2.00", "CRC"),
            ],
        )

    def test_parses_transaction_wrapped_across_lines(self):
        text = """
Purchases Made
123 12-NOV-25 ONLINE STORE ORDER
REFERENCE 987654 USD 1,234.56
Interest Charges
"""

        self.assertEqual(
            extract_purchases(text),
            [("12-NOV-25", "ONLINE STORE ORDER REFERENCE 987654", "1234.56", "USD")],
        )


if __name__ == "__main__":
    unittest.main()
