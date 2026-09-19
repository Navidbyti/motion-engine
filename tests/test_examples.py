import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from motion_engine.validation import load_spec, validate_schema, validate_semantics


class PublicFixtureTests(unittest.TestCase):
    def examples(self):
        for name in ("hello","weather","image-card"):
            yield load_spec(ROOT/"examples"/f"{name}.motion.json")

    def test_schema_copy_is_in_sync(self):
        root=json.loads((ROOT/"MotionSpec.schema.json").read_text(encoding="utf-8"))
        packaged=json.loads((ROOT/"src/motion_engine/MotionSpec.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(root,packaged)

    def test_public_examples_semantics(self):
        examples=list(self.examples())
        self.assertEqual([(x["project"]["locale"],x["canvas"]["width"],x["canvas"]["height"]) for x in examples],[("en-US",1920,1080),("ar-EG",1080,1080),("en-US",640,360)])
        for spec in examples:
            self.assertEqual(validate_semantics(spec),[])

    @unittest.skipUnless(importlib.util.find_spec("jsonschema"),"install project dependencies for full JSON Schema validation")
    def test_public_examples_schema(self):
        for spec in self.examples():
            self.assertEqual(validate_schema(spec),[])

    def test_duplicate_id_is_rejected(self):
        spec=copy.deepcopy(next(self.examples()))
        spec["timeline"][0]["elements"][1]["id"]="title"
        self.assertTrue(any("duplicate id" in e for e in validate_semantics(spec)))

    def test_bad_binding_is_rejected(self):
        spec=copy.deepcopy(list(self.examples())[1])
        spec["timeline"][0]["elements"][1]["dataBinding"]["field"]="not_a_column"
        self.assertTrue(any("unknown field" in e for e in validate_semantics(spec)))

if __name__=="__main__":
    unittest.main()
