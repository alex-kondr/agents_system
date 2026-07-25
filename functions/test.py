import sys
import os


current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)


from product_test.test_products_multiprocessing import Product, TestProductMultiprocessing, check_code_changes
from product_test.test_logs import LogProduct, TestLogProduct
import product_test.list_of_agents as agents


agent = agents.BUYMOBILE_AU
# agent = agents.TEST
reload = 1
session_id = 0


if __name__ == "__main__":
    product = Product(agent, reload=reload, session_id=session_id)
    print(product.result)
    test = TestProductMultiprocessing(product)
    test.run(xproduct_names=[], not_xproduct_name='', len_name=3, xreview_title=[], xreview_conclusion=[], xreview_excerpt=[])

    log = LogProduct(agent, reload=reload, session_id=session_id)
    test_log = TestLogProduct(log)
    test_log.test_log()

    check_code_changes(__file__)
