from django.conf import settings
from django.db import models


class LessonProgress(models.Model):
    """One row per (user, lesson). Lessons themselves live in fixtures/lessons.json.

    ``best_score`` rather than "last score": someone who passes a quiz and then
    retakes it carelessly while showing a neighbour has still learned the lesson.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="lesson_progress")
    lesson_id = models.CharField(max_length=32)
    attempts = models.PositiveSmallIntegerField(default=0)
    best_score = models.PositiveSmallIntegerField(default=0)
    total = models.PositiveSmallIntegerField(default=0)
    completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "lesson_id")]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.lesson_id} {self.best_score}/{self.total}"
