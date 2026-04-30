from django.core.management.base import BaseCommand

from resources.models import Tag, TagType


class Command(BaseCommand):
    help = "Seeds the database with Semester 1 through Semester 8 tags."

    def handle(self, *args, **options):
        created_count = 0
        for i in range(1, 9):
            tag, created = Tag.objects.get_or_create(
                name=f"Semester {i}",
                defaults={"type": TagType.SEMESTER},
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Created tag: {tag.name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Tag already exists: {tag.name}"))

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {created_count} semester tags."))
