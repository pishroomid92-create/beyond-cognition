import unittest

from workflow import summarize_workflow

ROLES = ["صورت‌بندی مسئله", "تحلیل‌گر", "فرضیه‌ساز", "منتقد", "ارزیاب شواهد", "ترکیب‌کننده"]

def steps(*roles):
    return [{"role": role} for role in roles]

class WorkflowSummaryTests(unittest.TestCase):
    def test_empty_workflow(self):
        result = summarize_workflow([], ROLES)
        self.assertEqual(result["completed_count"], 0)
        self.assertEqual(result["missing_roles"], ROLES)
        self.assertEqual(result["next_role"], ROLES[0])

    def test_all_roles_in_order(self):
        result = summarize_workflow(steps(*ROLES), ROLES)
        self.assertEqual(result["completed_count"], 6)
        self.assertEqual(result["missing_roles"], [])
        self.assertIsNone(result["next_role"])
        self.assertEqual(result["out_of_order"], [])

    def test_duplicate_does_not_inflate_progress(self):
        result = summarize_workflow(steps(ROLES[0], ROLES[0], ROLES[1]), ROLES)
        self.assertEqual(result["completed_count"], 2)
        self.assertEqual(result["duplicate_roles"], [ROLES[0]])
        self.assertEqual(result["next_role"], ROLES[2])

    def test_out_of_order_is_reported(self):
        result = summarize_workflow(steps(ROLES[0], ROLES[2], ROLES[1]), ROLES)
        self.assertEqual(result["out_of_order"], [ROLES[1]])
        self.assertEqual(result["completed_count"], 3)

    def test_optional_role_is_not_counted(self):
        result = summarize_workflow(steps("یادداشت پژوهشگر", ROLES[0]), ROLES)
        self.assertEqual(result["completed_count"], 1)
        self.assertEqual(result["next_role"], ROLES[1])

if __name__ == "__main__":
    unittest.main()
