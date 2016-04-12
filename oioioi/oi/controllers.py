from django.shortcuts import redirect
from django.template import RequestContext
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

from oioioi.base.utils.redirect import safe_redirect
from oioioi.contests.controllers import PublicContestRegistrationController, \
        PastRoundsHiddenContestControllerMixin
from oioioi.contests.models import Submission, SubmissionReport
from oioioi.contests.utils import is_contest_admin, is_contest_observer, \
        can_see_personal_data
from oioioi.programs.controllers import ProgrammingContestController
from oioioi.participants.controllers import ParticipantsController, \
        OnsiteContestControllerMixin
from oioioi.participants.models import Participant
from oioioi.participants.utils import is_participant
from oioioi.oi.models import OIRegistration
from oioioi.spliteval.controllers import SplitEvalContestControllerMixin
from oioioi.scoresreveal.utils import is_revealed


class OIRegistrationController(ParticipantsController):
    @property
    def form_class(self):
        from oioioi.oi.forms import OIRegistrationForm
        return OIRegistrationForm

    @property
    def participant_admin(self):
        from oioioi.oi.admin import OIRegistrationParticipantAdmin
        return OIRegistrationParticipantAdmin

    @classmethod
    def anonymous_can_enter_contest(cls):
        return True

    # Redundant because of filter_visible_contests, but saves a db query
    def can_enter_contest(self, request):
        return True

    @classmethod
    def filter_visible_contests(cls, request, contest_queryset):
        return contest_queryset

    def can_register(self, request):
        return True

    def can_unregister(self, request, participant):
        return False

    def registration_view(self, request):
        participant = self._get_participant_for_form(request)

        if 'oi_oiregistrationformdata' in request.session:
            # pylint: disable=not-callable
            form = self.form_class(request.session[
                                   'oi_oiregistrationformdata'])
            del request.session['oi_oiregistrationformdata']
        else:
            form = self.get_form(request, participant)
        if request.method == 'POST':
            if '_add_school' in request.POST:
                data = request.POST.copy()
                data.pop('_add_school', None)
                data.pop('csrfmiddlewaretoken', None)
                request.session['oi_oiregistrationformdata'] = data
                return redirect('add_school')
            elif form.is_valid():  # pylint: disable=maybe-no-member
                participant, created = Participant.objects \
                        .get_or_create(contest=self.contest, user=request.user)
                self.handle_validated_form(request, form, participant)
                if 'next' in request.GET:
                    return safe_redirect(request, request.GET['next'])
                else:
                    return redirect('default_contest_view',
                            contest_id=self.contest.id)

        context = {'form': form, 'participant': participant}
        return TemplateResponse(request, self.registration_template, context)

    def get_contest_participant_info_list(self, request, user):
        prev = super(OIRegistrationController, self) \
                .get_contest_participant_info_list(request, user)

        if can_see_personal_data(request):
            sensitive_info = OIRegistration.objects.filter(
                    participant__user=user,
                    participant__contest=request.contest)
            if sensitive_info.exists():
                context = {'model': sensitive_info[0]}
                rendered_sensitive_info = render_to_string(
                        'oi/sensitive_participant_info.html',
                        context_instance=RequestContext(request, context))
                prev.append((2, rendered_sensitive_info))

        return prev


class OIContestController(ProgrammingContestController):
    description = _("Polish Olympiad in Informatics - Online")
    create_forum = True
    show_email_in_participants_data = True

    def fill_evaluation_environ(self, environ, submission):
        super(OIContestController, self) \
                .fill_evaluation_environ(environ, submission)

        environ['group_scorer'] = 'oioioi.programs.utils.min_group_scorer'
        environ['test_scorer'] = \
                'oioioi.programs.utils.threshold_linear_test_scorer'

    def registration_controller(self):
        return OIRegistrationController(self.contest)

    def can_submit(self, request, problem_instance, check_round_times=True):
        if request.user.is_anonymous():
            return False
        if request.user.has_perm('contests.contest_admin', self.contest):
            return True
        if not is_participant(request):
            return False
        return super(OIContestController, self) \
                .can_submit(request, problem_instance, check_round_times)

    def can_see_stats(self, request):
        return is_contest_admin(request) or is_contest_observer(request)

    def should_confirm_submission_receipt(self, request, submission):
        return submission.kind == 'NORMAL' and request.user == submission.user

    def update_user_result_for_problem(self, result):
        try:
            latest_submission = Submission.objects \
                .filter(problem_instance=result.problem_instance) \
                .filter(user=result.user) \
                .filter(score__isnull=False) \
                .exclude(status='CE') \
                .filter(kind='NORMAL') \
                .latest()
            try:
                report = SubmissionReport.objects.get(
                        submission=latest_submission, status='ACTIVE',
                        kind='NORMAL')
            except SubmissionReport.DoesNotExist:
                report = None
            result.score = latest_submission.score
            result.status = latest_submission.status
            result.submission_report = report
        except Submission.DoesNotExist:
            result.score = None
            result.status = None
            result.submission_report = None

    def can_see_ranking(self, request):
        return is_contest_admin(request) or is_contest_observer(request)

    def default_contestlogo_url(self):
        return '%(url)soi/logo.png' % {'url': settings.STATIC_URL}

    def default_contesticons_urls(self):
        return ['%(url)simages/menu/menu-icon-%(i)d.png' %
                {'url': settings.STATIC_URL, 'i': i} for i in range(1, 4)]

OIContestController.mix_in(SplitEvalContestControllerMixin)


class OIOnsiteContestController(OIContestController):
    description = _("Polish Olympiad in Informatics - Onsite")

OIOnsiteContestController.mix_in(OnsiteContestControllerMixin)
OIOnsiteContestController.mix_in(PastRoundsHiddenContestControllerMixin)


class OIFinalOnsiteContestController(OIOnsiteContestController):
    description = _("Polish Olympiad in Informatics - Onsite - Finals")

    def can_see_submission_score(self, request, submission):
        return True

    def update_user_result_for_problem(self, result):
        submissions = Submission.objects \
            .filter(problem_instance=result.problem_instance) \
            .filter(user=result.user) \
            .filter(score__isnull=False) \
            .exclude(status='CE') \
            .filter(kind='NORMAL')

        if submissions:
            max_submission = submissions.order_by('-score')[0]

            try:
                report = SubmissionReport.objects.get(
                        submission=max_submission, status='ACTIVE',
                        kind='NORMAL')
            except SubmissionReport.DoesNotExist:
                report = None

            result.score = max_submission.score
            result.status = max_submission.status
            result.submission_report = report
        else:
            result.score = None
            result.status = None
            result.submission_report = None


class BOIOnsiteContestController(OIOnsiteContestController):
    description = _("Baltic Olympiad in Informatics")
    create_forum = False

    def can_see_test_comments(self, request, submissionreport):
        submission = submissionreport.submission
        return is_contest_admin(request) or \
                self.results_visible(request, submission)

    def reveal_score(self, request, submission):
        super(BOIOnsiteContestController, self).reveal_score(request,
                submission)
        self.update_user_results(submission.user, submission.problem_instance)

    def update_user_result_for_problem(self, result):
        try:
            submissions = Submission.objects \
                .filter(problem_instance=result.problem_instance) \
                .filter(user=result.user) \
                .filter(score__isnull=False) \
                .exclude(status='CE') \
                .filter(kind='NORMAL')

            chosen_submission = submissions.latest()

            revealed = submissions.filter(revealed__isnull=False)
            if revealed:
                max_revealed = revealed.order_by('-score')[0]
                if max_revealed.score > chosen_submission.score:
                    chosen_submission = max_revealed

            try:
                report = SubmissionReport.objects.get(
                        submission=chosen_submission, status='ACTIVE',
                        kind='NORMAL')
            except SubmissionReport.DoesNotExist:
                report = None

            result.score = chosen_submission.score
            result.status = chosen_submission.status
            result.submission_report = report
        except Submission.DoesNotExist:
            result.score = None
            result.status = None
            result.submission_report = None

    def get_visible_reports_kinds(self, request, submission):
        if is_revealed(submission) or \
                self.results_visible(request, submission):
            return ['USER_OUTS', 'INITIAL', 'NORMAL']
        else:
            return ['USER_OUTS', 'INITIAL']

    def can_print_files(self, request):
        return True

    def can_see_ranking(self, request):
        return True

    def default_contestlogo_url(self):
        return None

    def default_contesticons_urls(self):
        return []

    def fill_evaluation_environ(self, environ, submission):
        super(BOIOnsiteContestController, self) \
                .fill_evaluation_environ(environ, submission)

        environ['test_scorer'] = 'oioioi.programs.utils.discrete_test_scorer'


class BOIOnlineContestController(BOIOnsiteContestController):
    description = _("Baltic Olympiad in Informatics - online")
    create_forum = False

    def registration_controller(self):
        return PublicContestRegistrationController(self.contest)

    def is_onsite(self):
        return False

    def can_see_ranking(self, request):
        return True
