import requests
import logging
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter

from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

LOG = logging.getLogger(__name__)
disable_warnings(InsecureRequestWarning)
DEFAULT_HEADERS = {
    'User-Agent': "docker/19.01.0-ce",
    'Accept-Encoding': ', '.join(('gzip', 'deflate')),
    'Accept': '*/*',
    'Connection': 'keep-alive',
    'Content-Type': 'application/json',
}


class ClientError(ConnectionError):
    pass


class GcrClient(requests.Session):
    def __init__(self, base_url, headers: dict = None):
        super(GcrClient, self).__init__()
        self.base_url = base_url
        self.verify = False
        if not headers:
            headers = {}
        self.headers.update(DEFAULT_HEADERS)
        self.headers.update(headers)
        self.mount("http://", HTTPAdapter(max_retries=3))
        self.mount("https://", HTTPAdapter(max_retries=3))

    def url(self, path):
        return urljoin(self.base_url, path)

    @classmethod
    def result_or_raise(cls, response, json=True):
        status_code = response.status_code

        if status_code // 100 != 2:
            msg = "[Status Code {}]: {}".format(status_code, response.text)
            LOG.warning(msg)
            raise ClientError(msg)
        if json:
            return response.json()
        return response.text

    def is_valid(self):
        path = "/v2/"
        rsp = self.get(self.url(path))
        try:
            rsp.json()
        except ValueError as e:
            LOG.error(e)
            return False
        return True

    def get_project_by_namespace(self, namespace):
        path = "/v2/{namespace}/tags/list".format(namespace=namespace)
        result = self.result_or_raise(self.get(self.url(path)))
        return result['child']

    def get_project_tags(self, project_name, namespace=None):
        if namespace:
            path = "/v2/{namespace}/{project}/tags/list" \
                .format(namespace=namespace, project=project_name)
        else:
            path = "/v2/{project}/tags/list" \
                .format(namespace=namespace, project=project_name)
        result = self.result_or_raise(self.get(self.url(path)))
        return result['tags']


if __name__ == "__main__":
    k8s = GcrClient("https://k8s.gcr.io")
    print("kube-apiserver-amd64")
    print(k8s.get_project_tags("kube-apiserver-amd64"))

    kaniko = GcrClient("https://gcr.io")
    print("kaniko-project")
    print(kaniko.get_project_by_namespace("kaniko-project"))
    print(kaniko.get_project_tags("executor", "kaniko-project"))
