from django.db import models


class Episode(models.Model):
    title = models.CharField(max_length=512)
    airdate = models.CharField(max_length=128, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("title", "airdate"),
                name="game_episode_title_airdate_uniq",
            ),
        ]

    def __str__(self) -> str:
        return self.title


class Quote(models.Model):
    episode = models.ForeignKey(
        Episode,
        on_delete=models.CASCADE,
        related_name="quotes",
        db_index=True,
    )
    text = models.TextField()

    def __str__(self) -> str:
        return self.text[:80]
