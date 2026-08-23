from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.test import SimpleTestCase
from django.urls import resolve


class DeferredInformationalRouteTests(SimpleTestCase):
    routes = {
        "/about/": ("apps.core.views.about", "core/about.html"),
        "/faq/": ("apps.core.views.faq", "core/faq.html"),
        "/branches/": ("apps.branches.views.branches", "branches/branches.html"),
        "/blog/": ("apps.blog.views.blog", "blog/blog.html"),
        "/blog/article/": ("apps.blog.views.article", "blog/article.html"),
        "/reviews/": ("apps.reviews.views.reviews", "reviews/reviews.html"),
        "/contact/": ("apps.contact.views.contact", "contact/contact.html"),
    }

    def test_deferred_routes_keep_their_existing_names_without_fabricated_templates(self):
        for path, (view_path, template_name) in self.routes.items():
            with self.subTest(path=path):
                match = resolve(path)
                actual_view = f"{match.func.__module__}.{match.func.__name__}"
                self.assertEqual(actual_view, view_path)
                with self.assertRaises(TemplateDoesNotExist):
                    get_template(template_name)

    def test_deferred_routes_are_not_linked_from_active_navigation(self):
        with open("templates/includes/navbar.html", encoding="utf-8") as source:
            navigation = source.read()
        with open("templates/includes/footer.html", encoding="utf-8") as source:
            navigation += source.read()
        for path, (view_path, _) in self.routes.items():
            namespace = view_path.split(".")[1]
            route_name = f"{namespace}:{view_path.rsplit('.', 1)[1]}"
            route_tokens = (path, f"'{route_name}'", f'"{route_name}"')
            with self.subTest(path=path):
                self.assertFalse(any(token in navigation for token in route_tokens))
