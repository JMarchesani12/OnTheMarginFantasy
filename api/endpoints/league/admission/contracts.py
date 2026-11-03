"""Admission failures independent of HTTP and legacy exception translation."""


class AdmissionDenied(Exception):
    code = 'admission_denied'


class AdmissionRejected(Exception):
    code = 'admission_rejected'
