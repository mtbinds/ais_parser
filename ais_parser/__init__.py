from pkg_resources import get_distribution, resource_filename

try:
    __version__ = get_distribution(__name__).version
except:
    __version__ = '1.0'

def get_resource_filename(resource_name):

    return resource_filename(__name__, resource_name)
