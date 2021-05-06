import io
import logging
import os
import zipfile

EXPORT_COMMANDS = [('status', 'report status of this repository.')]

def load(options, readonly=False):
    assert 'path' in options

    if 'extensions' in options:
        allowed_extensions = options['extensions'].split(',')
    else:
        allowed_extensions = None

    if 'recursive' in options:
        recursive = bool(options['recursive'])
    else:
        recursive = True

    if 'unzip' in options:
        unzip = bool(options['unzip'])
    else:
        unzip = False

    return FileRepository(options['path'], allowedExtensions=allowed_extensions,
                          recursive=recursive, unzip=unzip)

class FileRepository:

    def __init__(self, path, allowedExtensions=None, recursive=True, unzip=False):
        self.root = path
        self.allowed_extensions = allowedExtensions
        self.recursive = recursive
        self.unzip = unzip

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def status(self):
        print("Folder at {}".format(self.root))

    def iterfiles(self):
        """
        Itérer les fichiers dans ce référentiel de fichiers. Renvoie un générateur de 3 tuples,
        contenant un handle, un nom de fichier et une extension de fichier du fichier actuellement ouvert.

        """
        logging.debug("Iterating files in " + self.root)
        failed_files = []
        for root, _, files in os.walk(self.root):
            # itérer les fichiers, filtrer uniquement les extensions autorisées
            for filename in files:
                _, ext = os.path.splitext(filename)
                if self.allowed_extensions == None or ext in self.allowed_extensions:
                    # heurtant des erreurs lors du décodage des données, iso-8859-1 semble les trier
                    with open(os.path.join(root, filename), 'r', encoding='iso-8859-1') as fp:
                        yield (fp, filename, ext)
                # extraction automatique du fichier zip
                elif self.unzip and ext == '.zip':
                    try:
                        with zipfile.ZipFile(os.path.join(root, filename), 'r') as z:
                            for zname in z.namelist():
                                _, ext = os.path.splitext(zname)
                                if self.allowed_extensions == None or ext in self.allowed_extensions:
                                    with z.open(zname, 'r') as fp:
                                        # zipfile renvoie un fichier binaire, nous avons donc besoin d'un
                                        # TextIOWrapper pour le décoder
                                        yield (io.TextIOWrapper(fp, encoding='iso-8859-1'), zname, ext)
                    except (zipfile.BadZipFile, RuntimeError) as error:
                        logging.warning("Unable to Extract zip File %s: %s ", filename, error)
                        failed_files.append(filename)
            # extraction automatique du fichier zip
            if not self.recursive:
                break
        if len(failed_files) > 0:
            logging.warning("Skipped %d Files Due to Errors: %s", len(failed_files), repr(failed_files))

    def close(self):
        pass
