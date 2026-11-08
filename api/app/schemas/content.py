"""The fixed vocabularies of the course structure (SE document §8)."""

from typing import Literal

# What an activity is for (FR-4.3). Mastery and review items count towards an objective's result
# (FR-7); a diagnostic item only picks module 0's refreshers (FR-8.1); a bonus quest gives points
# but never affects mastery (FR-8.3).
Purpose = Literal["practice", "diagnostic", "retrieval", "mastery", "review", "bonus"]

# What a module's step is (FR-2.2).
SegmentKind = Literal["video", "text", "worked_example", "activity", "refresher"]
