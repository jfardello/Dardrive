from setuptools import setup, find_packages
import sys
import os
import imp

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()
NEWS = open(os.path.join(here, 'NEWS.txt')).read()


ver_file = os.path.join(os.path.dirname(__file__), "src/dardrive/__init__.py")
ver = imp.load_source('ver', ver_file)
version = ver.__release__

install_requires = [
    'sqlalchemy',
    'setuptools',
    'xattr'
]


setup(name='dardrive',
      version=version,
      description="A dar based backup tool",
      long_description=README + '\n\n' + NEWS,
      classifiers=[
        'System :: Archiving :: Backup',
      ],
      keywords='backup dar cli',
      author='Jos\xc3\xa9 Manuel Fardello',
      author_email='jmfardello@gmail.com',
      test_suite="dardrive.tests.suite",
      url='',
      license='GPLv3',
      packages=find_packages('src'),
      package_dir={'': 'src'},
      include_package_data=True,
      package_data={'dardrive': ['tests/*.cfg']},
      zip_safe=False,
      install_requires=install_requires,
      entry_points={
        'console_scripts': [
            'dardrive = dardrive.shell:main',
            'dar_par_create.duc = dardrive.dar:dar_par_create',
            'dar_par_test.duc = dardrive.dar:dar_par_test',
            'dardrive_move = dardrive.dar:dar_move',
        ]
      }
)
