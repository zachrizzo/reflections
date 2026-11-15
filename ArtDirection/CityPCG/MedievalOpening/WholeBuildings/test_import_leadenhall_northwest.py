"""Run the exact-package and failure-path tests against northwest Leadenhall."""

import unittest

import import_leadenhall_northwest as importer
from test_import_west_connector import ReviewedImportChecks


class LeadenhallNorthwestImportTests(ReviewedImportChecks, unittest.TestCase):
    entry = importer
    destination = '/Game/GrayLondon/MedievalOpening/WholeBuildings/LeadenhallNorthwest'
    names = (
        'SM_GLMedieval_LeadenhallNorthwest_TradingRange_06ebfe6e',
        'SM_GLMedieval_LeadenhallNorthwest_DeepWorkshop_9059607e',
        'SM_GLMedieval_LeadenhallNorthwest_SteppedMarket_99e572dd',
        'SM_GLMedieval_LeadenhallNorthwest_DeepWorkshop_ee3443af',
    )


if __name__ == '__main__':
    unittest.main()
