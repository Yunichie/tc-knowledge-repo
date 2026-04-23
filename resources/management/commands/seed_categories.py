from django.core.management.base import BaseCommand
from django.utils.text import slugify

from resources.models import Category


class Command(BaseCommand):
    help = "Seeds the database with initial categories."

    def handle(self, *args, **options):
        initial_categories = [
            {"name": "Syllabus", "description": "Course outlines and syllabi for classes."},
            {"name": "Lecture Notes", "description": "Slides and notes from lectures."},
            {"name": "Assignments", "description": "Past assignments and project descriptions."},
            {"name": "Exams", "description": "Past exams and quizzes for practice."},
            {"name": "Research Papers", "description": "Published papers and research material."},
            {"name": "Tutorials", "description": "Guides and tutorials for technical skills."},
            {"name": "General", "description": "Any resources that do not fit into any other category."},
        ]

        created_count = 0
        for cat_data in initial_categories:
            cat, created = Category.objects.get_or_create(
                name=cat_data["name"],
                defaults={
                    "slug": slugify(cat_data["name"]),
                    "description": cat_data["description"],
                },
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Created category: {cat.name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Category already exists: {cat.name}"))

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {created_count} categories."))
