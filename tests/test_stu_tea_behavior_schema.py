import unittest

from vbas.schemas.stu_tea_behavior import (
    StudentBehaviorRequest,
    Stu_Tea_BehaviorRequest,
    TeacherBehaviorImageResult,
    TeacherBehaviorRequest,
)


class StuTeaBehaviorSchemaTest(unittest.TestCase):
    def test_teacher_behavior_thresholds_are_optional_request_fields(self):
        request = Stu_Tea_BehaviorRequest(
            ImageList=[],
            Teacher_Behavior_Thresd={
                "sit": 0.7,
                "stand": 0.6,
            },
        )

        self.assertEqual(request.Teacher_Behavior_Thresd.sit, 0.7)
        self.assertEqual(request.Teacher_Behavior_Thresd.stand, 0.6)
        self.assertIsNone(request.Teacher_Behavior_Thresd.bbwriting)
        self.assertIsNone(request.Teacher_Behavior_Thresd.teach)

    def test_removed_head_pose_flag_is_ignored_for_old_clients(self):
        request = TeacherBehaviorRequest(ImageList=[], ReturnHeadPose=True)
        self.assertNotIn("ReturnHeadPose", request.model_dump())
        self.assertNotIn("ReturnHeadPose", TeacherBehaviorRequest.model_json_schema()["properties"])

    def test_student_behavior_thresholds_use_simplified_request_fields(self):
        request = StudentBehaviorRequest(
            ImageList=[],
            Student_Thresd={
                "phone": 0.5,
                "hand": 0.99,
                "sleep": 0.45,
                "stand": 0.99,
                "read": 0.5,
            },
        )

        self.assertEqual(request.Student_Thresd.phone, 0.5)
        self.assertEqual(request.Student_Thresd.hand, 0.99)
        self.assertEqual(request.Student_Thresd.sleep, 0.45)
        self.assertEqual(request.Student_Thresd.stand, 0.99)
        self.assertEqual(request.Student_Thresd.read, 0.5)

    def test_teacher_response_has_only_behavior_fields(self):
        result = TeacherBehaviorImageResult(
            StatusObject={"StatusString": "success", "StatusCode": 0},
            ResultList=[],
        )
        self.assertEqual(set(result.model_dump()), {"StatusObject", "ResultList"})


if __name__ == "__main__":
    unittest.main()
