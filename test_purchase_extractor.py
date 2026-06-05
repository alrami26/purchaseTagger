import unittest
from unittest.mock import patch

from purchase_extractor import process_purchases, extract_purchases


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

    def test_process_purchases_accepts_bac_debit_type(self):
        with patch("purchase_extractor.extract_text", return_value=""), \
                patch("purchase_extractor.load_tags", return_value={}):
            self.assertEqual(process_purchases("statement.pdf", bank="BAC", account_type="Debito"), [])

    def test_process_purchases_treats_bac_credit_purchases_as_negative_and_refunds_as_positive(self):
        text = """
Purchases Made
123 11-AGO-25 STORE PURCHASE USD 20.00
124 12-AGO-25 REFUND MERCHANT USD -5.00
Interest Charges
"""

        with patch("purchase_extractor.extract_text", return_value=text), \
                patch("purchase_extractor.load_tags", return_value={}):
            purchases = process_purchases("statement.pdf", bank="BAC", account_type="Credito")

        self.assertEqual(
            purchases,
            [
                ("11-AGO-25", "STORE PURCHASE", "-20.00", "USD", "N/A", 0),
                ("12-AGO-25", "REFUND MERCHANT", "5.00", "USD", "N/A", 0),
            ],
        )

    def test_process_purchases_extracts_bac_credit_payments_as_positive_credits(self):
        text = """
Movimientos de la tarjeta de crédito
                                       Transacción          Interés en         Transacción          Interés en
                                        en colones           colones            en dólares           dólares

A) Detalle de pago del periodo
N. Referencia    Fecha de pago              Concepto/Descripción                Transacción       Interés en      Transacción       Interés en
                                                                                 en colones         colones         en dólares        dólares

0319136009494      19-MAR-26     PAGO RECIBIDO...136                                                                     386.51-            3.44-
0323136009497      23-MAR-26     PAGO RECIBIDO...136                              776,714.88-        13,209.05-
Total de pagos recibidos                                                          776,714.88-        13,209.05-          386.51-            3.44-

B) Detalle de compras del periodo
N. Referencia    Fecha de pago            Concepto/Descripción                   Lugar          Moneda          Monto en           Monto en
                                                                                                                  colones            dólares

031580013595       15-MAR-26     I.C.E. PAGUELO 84169890                                          CRC               10,560.03
C) Detalle de intereses
"""

        with patch("purchase_extractor.extract_text", return_value=text) as extract_text, \
                patch("purchase_extractor.load_tags", return_value={}):
            purchases = process_purchases("statement.pdf", bank="BAC", account_type="Credito")

        extract_text.assert_called_once_with("statement.pdf", layout=True)
        self.assertEqual(
            purchases,
            [
                ("19-MAR-26", "PAGO RECIBIDO...136", "386.51", "USD", "N/A", 0),
                ("23-MAR-26", "PAGO RECIBIDO...136", "776714.88", "CRC", "N/A", 0),
                ("15-MAR-26", "I.C.E. PAGUELO 84169890", "-10560.03", "CRC", "N/A", 0),
            ],
        )

    def test_process_purchases_extracts_all_bac_debit_column_movements_with_signed_direction(self):
        text = """
Nombre: SAMPLE USER
Cuenta IBAN: CR29 0102 0000 9385 9819 00
Moneda: COLONES
3101012009 30/ABR/26
     NO. REFERENCIA                    FECHA                                         CONCEPTO                                             DÉBITOS               CRÉDITOS
          966882466                    MAR/31         SINPE MOVIL Pishas_________                                                                  4,150.00
          406417547                    ABR/01         TEF DE:REGINALDO JESUS FLORES                                                                                      5,177.00
          950507539                    ABR/06         CD SINPE A 15103510010019391                                                              117,500.00
          950507539                    ABR/06         COMISION CD SINPE A 1510351001                                                               471.00
          043076342                    ABR/30         INTERESES                                                                                                           418.18
ÚLTIMA LÍNEA                                                                         SALDO AL CORTE                                                                 283,218.70
"""

        with patch("purchase_extractor.extract_text", return_value=text) as extract_text, \
                patch("purchase_extractor.load_tags", return_value={}):
            purchases = process_purchases("statement.pdf", bank="BAC", account_type="Debito")

        extract_text.assert_called_once_with("statement.pdf", layout=True)
        self.assertEqual(
            purchases,
            [
                ("31-MAR-26", "SINPE MOVIL Pishas_________", "-4150.00", "CRC", "N/A", 0),
                ("01-ABR-26", "TEF DE:REGINALDO JESUS FLORES", "5177.00", "CRC", "N/A", 0),
                ("06-ABR-26", "CD SINPE A 15103510010019391", "-117500.00", "CRC", "N/A", 0),
                ("06-ABR-26", "COMISION CD SINPE A 1510351001", "-471.00", "CRC", "N/A", 0),
                ("30-ABR-26", "INTERESES", "418.18", "CRC", "N/A", 0),
            ],
        )

    def test_process_purchases_uses_previous_year_for_prior_december_debit_movements(self):
        text = """
Moneda: DOLARES
3101012009 31/ENE/26
     NO. REFERENCIA                    FECHA                                         CONCEPTO                                             DÉBITOS               CRÉDITOS
          123456789                    DIC/31         ATM WITHDRAWAL                                                                                20.00
ÚLTIMA LÍNEA                                                                         SALDO AL CORTE                                                                     1.00
"""

        with patch("purchase_extractor.extract_text", return_value=text), \
                patch("purchase_extractor.load_tags", return_value={}):
            purchases = process_purchases("statement.pdf", bank="BAC", account_type="Debito")

        self.assertEqual(
            purchases,
            [("31-DIC-25", "ATM WITHDRAWAL", "-20.00", "USD", "N/A", 0)],
        )

    def test_process_purchases_extracts_promerica_credit_payments_positive_and_reversals_positive(self):
        text = """
Fecha de Corte                                                                                               26/12/2025

                                                                                            Detalle de pagos del periodo
           Fecha de Pagos                             Concepto / Descripción                                                                colones                     colones                       en US$                        US$
                11/12/2025                    PAGO SINPE                                                                                       -96,711.06                  -10,626.33                             0.00                      0.00

                                                                                            Detalle de compras del periodo
    Fecha de la transacción                            Concepto / Descripción                                                                 Lugar / Moneda                            colones                          US$
               12/12/2025                      REVERSIÓN COMPRA                                                                         SAN JOSE                     CR                     -1,200.00                           0.00
               13/12/2025                      REFUND STORE                                                                            MIAMI                        US                         0.00                      -35.50
        """

        with patch("purchase_extractor.extract_text", return_value=text), \
                patch("purchase_extractor.load_tags", return_value={}):
            purchases = process_purchases("promerica.pdf", bank="Promerica", account_type="Credito")

        self.assertEqual(
            purchases,
            [
                ("11-DIC-25", "PAGO SINPE", "96711.06", "CRC", "N/A", 0),
                ("12-DIC-25", "REVERSIÓN COMPRA", "1200.00", "CRC", "N/A", 0),
                ("13-DIC-25", "REFUND STORE", "35.50", "USD", "N/A", 0),
            ],
        )

    def test_process_purchases_extracts_promerica_credit_non_credit_movements(self):
        text = """
Fecha de Corte                                                                                               26/12/2025

                                                                                            Detalle de pagos del periodo
           Fecha de Pagos                             Concepto / Descripción                                                                colones                     colones                       en US$                        US$
                11/12/2025                    PAGO SINPE                                                                                       -96,711.06                  -10,626.33                             0.00                      0.00

                                                                                            Detalle de compras del periodo

                                                                                                                                                                                       Monto en                      Monto en
    Fecha de la transacción                            Concepto / Descripción                                                                 Lugar / Moneda                            colones                          US$

               28/11/2025                      FUNERARIA POLINI                                                                           SAN JOSE                     CR                      5,000.00                           0.00
               15/12/2025                      INS550230PRISSANPED                                                                        MONTES DE OCA                CR                           0.00                       291.84
             23/12/2025                    TARGET        00008151                                                                  FORT LAUDERDA                US                         0.00                      121.51
                                             Total de compras del periodo de                           26/11/2025              al                                                                            5,785.00                              900.3026/12/2025

                                                                                                  Detalle de intereses
                                                    Concepto / Descripción                                                                                       colones                                US$
MONTO POR INTERESES CORRIENTES                                                                                                                                     7,511.06                             34.46
MONTO POR INTERESES MORATORIOS                                                                                                                                        0.00                               0.00
                                            Total por concepto de intereses                                                                                         18,295.11                                    78.10

                                                                                               Detalle de otros cargos
        Fecha de Pagos                             Concepto / Descripción                                                      Lugar / Moneda                           colones                            US$
                                       Total por concepto de otros cargos                                                                                                               0.00                                      0.00

                                                                  Detalle de productos y servicios de elección voluntaria*
                Fecha                                Concepto / Descripción                                             Lugar / Moneda                           Colones                            US$
            02/12/2025                              SEGURO PROTECCIÓN FINANC. TC 1 - SAGICOR                    SAN JOSE                      CRI                                 3,400.00                                      0.00
        """

        with patch("purchase_extractor.extract_text", return_value=text) as extract_text, \
                patch("purchase_extractor.load_tags", return_value={}):
            purchases = process_purchases("promerica.pdf", bank="Promerica", account_type="Credito")

        extract_text.assert_called_once_with("promerica.pdf", layout=True)
        self.assertEqual(
            purchases,
            [
                ("11-DIC-25", "PAGO SINPE", "96711.06", "CRC", "N/A", 0),
                ("28-NOV-25", "FUNERARIA POLINI", "-5000.00", "CRC", "N/A", 0),
                ("15-DIC-25", "INS550230PRISSANPED", "-291.84", "USD", "N/A", 0),
                ("23-DIC-25", "TARGET 00008151", "-121.51", "USD", "N/A", 0),
                ("26-DIC-25", "MONTO POR INTERESES CORRIENTES", "-7511.06", "CRC", "N/A", 0),
                ("26-DIC-25", "MONTO POR INTERESES CORRIENTES", "-34.46", "USD", "N/A", 0),
                ("02-DIC-25", "SEGURO PROTECCIÓN FINANC. TC 1 - SAGICOR", "-3400.00", "CRC", "N/A", 0),
            ],
        )

    def test_process_purchases_rejects_promerica_debit_combination(self):
        with self.assertRaises(ValueError):
            process_purchases("statement.pdf", bank="Promerica", account_type="Debito")

    def test_process_purchases_rejects_unsupported_bank_or_type(self):
        with self.assertRaises(ValueError):
            process_purchases("statement.pdf", bank="Other", account_type="Credito")
        with self.assertRaises(ValueError):
            process_purchases("statement.pdf", bank="BAC", account_type="Other")


if __name__ == "__main__":
    unittest.main()
