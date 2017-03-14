from django.conf.urls import url

from oioioi.zeus import views

noncontest_patterns = [
    url(r'^s/(?P<saved_environ_id>[-:a-zA-Z0-9]+)/push_grade/'
        r'(?P<signature>[\w\d:-]+)/$',
        views.push_grade, name='zeus_push_grade_callback'),
]
