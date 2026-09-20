import unittest
from erp_client import NexacroSSVParser, SSVPayloadBuilder

class TestSSVParser(unittest.TestCase):
    def setUp(self):
        # RS = ASCII 30, US = ASCII 31
        self.RS = '\x1E'
        self.US = '\x1F'
        self.NULL_CHAR = '\x03'
        
    def test_parse_valid_ssv(self):
        # 모의 데이터: Dataset ID: ds_result, 컬럼: COL1, COL2
        ssv_text = (
            "SSV:utf-8" + self.RS +
            "Dataset:ds_result" + self.RS +
            "_RowType_" + self.US + "COL1:STRING(256)" + self.US + "COL2:INT(10)" + self.RS +
            "N" + self.US + "Value1" + self.US + "100" + self.RS +
            "I" + self.US + "Value2" + self.US + "200" + self.RS
        )
        
        parsed = NexacroSSVParser.parse_ssv_response(ssv_text)
        
        self.assertIn("ds_result", parsed)
        rows = parsed["ds_result"]
        self.assertEqual(len(rows), 2)
        
        self.assertEqual(rows[0]["COL1"], "Value1")
        self.assertEqual(rows[0]["COL2"], "100")
        
        self.assertEqual(rows[1]["COL1"], "Value2")
        self.assertEqual(rows[1]["COL2"], "200")
        
    def test_parse_null_character(self):
        # 널 문자가 포함된 데이터
        ssv_text = (
            "SSV:utf-8" + self.RS +
            "Dataset:ds_test" + self.RS +
            "_RowType_" + self.US + "COL_A:STRING(10)" + self.US + "COL_B:STRING(10)" + self.RS +
            "N" + self.US + "Data A" + self.US + self.NULL_CHAR + self.RS
        )
        parsed = NexacroSSVParser.parse_ssv_response(ssv_text)
        rows = parsed["ds_test"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["COL_A"], "Data A")
        self.assertEqual(rows[0]["COL_B"], "") # 널 문자는 빈 문자열로 파싱되어야 함
        
    def test_build_payload(self):
        data = {
            "ds_req": {
                "columns": ["ITEM_CD", "REQ_QTY"],
                "rows": [
                    ["MODEL_A", "10"],
                    ["MODEL_B", ""] # 빈 값은 NULL_CHAR로 변환되어야 함
                ]
            }
        }
        
        result = SSVPayloadBuilder.build_payload(data)
        
        self.assertTrue(result.startswith("SSV:utf-8" + self.RS))
        self.assertIn("Dataset:ds_req" + self.RS, result)
        self.assertIn("_RowType_" + self.US + "ITEM_CD:STRING(256)" + self.US + "REQ_QTY:STRING(256)" + self.RS, result)
        self.assertIn("N" + self.US + "MODEL_A" + self.US + "10" + self.RS, result)
        self.assertIn("N" + self.US + "MODEL_B" + self.US + self.NULL_CHAR + self.RS, result)

    def test_build_payload_preserve_empty(self):
        data = {
            "ds_req": {
                "columns": ["COL1", "COL2", "COL3"],
                "rows": [["", None, "VALUE"]],
            }
        }

        result = SSVPayloadBuilder.build_payload(data, null_for_empty=False)

        self.assertIn(
            "N" + self.US + "" + self.US + self.NULL_CHAR + self.US + "VALUE" + self.RS,
            result,
        )

    def test_build_payload_separates_datasets(self):
        data = {
            "ds_a": {
                "columns": ["A"],
                "rows": [["1"]],
            },
            "ds_b": {
                "columns": ["B"],
                "rows": [["2"]],
            },
        }

        result = SSVPayloadBuilder.build_payload(data, null_for_empty=False)

        self.assertIn(
            "N" + self.US + "1" + self.RS + self.RS + "Dataset:ds_b" + self.RS,
            result,
        )

if __name__ == "__main__":
    unittest.main()
