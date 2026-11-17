import importlib
import sys
import types
import unittest

import numpy as np


class TeacherBehaviorServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._original_modules = {
            name: sys.modules.get(name)
            for name in (
                "vbas.core.settings",
                "vbas.services.teacher_behavior_service",
                "vbas.services.capacity_service",
            )
        }
        sys.modules.pop("vbas.services.teacher_behavior_service", None)
        settings_stub = types.SimpleNamespace(
            Teacher_Behavior_Thresd={
                "MergeIoU": 0.8,
                "ImageSize": 640,
                "sit": 0.4,
                "stand": 0.4,
                "bbwriting": 0.25,
                "teach": 0.25,
                "KeepOnlyMainSubject": True,
                "MainSubjectStrategy": "posture_confidence",
                "SubjectClusterIoU": 0.45,
                "PostureConflictRatio": 0.10,
                "PostureConflictDefault": "stand",
                "ForcePostureWhenMissing": True,
            },
        )
        sys.modules["vbas.core.settings"] = types.SimpleNamespace(
            yolo_teacher_behavior_model=types.SimpleNamespace(),
            settings=settings_stub,
            use_half=False,
        )
        sys.modules["vbas.services.capacity_service"] = types.SimpleNamespace(
            increment_connection=lambda: None,
            increment_processed_images=lambda count: None,
        )
        self.service = importlib.import_module("vbas.services.teacher_behavior_service")

    def tearDown(self):
        sys.modules.pop("vbas.services.teacher_behavior_service", None)
        for name, module in self._original_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    async def test_teacher_v1_returns_behavior_without_head_pose(self):
        from vbas.schemas.stu_tea_behavior import ImageItem, TeacherBehaviorRequest

        teacher_position = self.service.ObjectPosition(
            LeftTopX=10,
            LeftTopY=20,
            RightBtmX=110,
            RightBtmY=220,
            Confidence=0.92,
        )
        behavior_results = {
            "platform_person": [teacher_position],
            "standing": [teacher_position],
            "sitting": [],
            "writing": [],
            "teaching": [],
        }
        details = [{
            "position": teacher_position,
            "positions": {"platform_person": teacher_position, "standing": teacher_position},
            "confidences": {"platform_person": 0.92, "standing": 0.92},
            "best_by_behavior": {},
        }]

        self.service.load_behavior_image = lambda image_item: np.zeros((300, 300, 3), dtype=np.uint8)
        self.service.process_teacher_behavior_model_detection_with_details = (
            lambda img, offset, img_size, thresholds: (behavior_results, details)
        )

        response = await self.service.analyze_teacher_behavior_by_model(
            TeacherBehaviorRequest(
                ImageList=[ImageItem(StoragePath="x.jpg", ImageId="img-1")],
                ReturnHeadPose=True,
            )
        )

        results = response.DataList[0].ResultList
        self.assertEqual([item.ObjectType for item in results], [100, 201, 202, 203, 204])
        self.assertEqual([item.ObjectCount for item in results], [1, 0, 1, 0, 0])
        self.assertNotIn("HeadPoseResult", response.model_dump()["DataList"][0])
        self.assertFalse(hasattr(self.service, "analyze_teacher_head_pose"))



if __name__ == "__main__":
    unittest.main()
