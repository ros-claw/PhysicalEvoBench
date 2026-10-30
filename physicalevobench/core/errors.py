"""Failure attribution is separate from task performance; no automatic retries."""


class ExperimentError(RuntimeError):
    category='UNKNOWN_FAILURE'


class ParticipantError(ExperimentError):
    category='PARTICIPANT_INVALID'


class ParticipantFormatError(ParticipantError):
    pass


class ParticipantBudgetExceeded(ParticipantError):
    category='PARTICIPANT_BUDGET_EXCEEDED'


class ProviderError(ExperimentError):
    category='PROVIDER_UNAVAILABLE'


class ProviderAuthError(ProviderError):
    category='PROVIDER_AUTH_ERROR'


class ProviderTransportError(ProviderError):
    category='PROVIDER_TRANSPORT_ERROR'


class ProviderDeadline(ProviderError):
    category='PROVIDER_DEADLINE_UNKNOWN'


class ProviderUsageUnknown(ProviderError):
    category='PROVIDER_USAGE_UNKNOWN'


class InitializationInvalid(ExperimentError):
    category='INIT_INVALID'


class RuntimeInfrastructureError(ExperimentError):
    category='RUNTIME_INFRA_ERROR'
