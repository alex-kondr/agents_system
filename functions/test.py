from test_products_multiprocessing import Product, TestProductMultiprocessing, check_code_changes
from test_logs import LogProduct, TestLogProduct



agent = "20076"
# agent = agents.TEST
reload = 1
session_id = 0

# excerpt: 5

if __name__ == "__main__":
    product = Product(agent, reload=reload, session_id=session_id)
    print(product.result)
    test = TestProductMultiprocessing(product)
    test.run(xproduct_names=[], not_xproduct_name='', len_name=3, xreview_title=[], xreview_conclusion=[], xreview_excerpt=[])

    log = LogProduct(agent, reload=reload, session_id=session_id)
    test_log = TestLogProduct(log)
    test_log.test_log()

    # check_code_changes(__file__)
