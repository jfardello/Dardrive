from setuptools import setup, find_packages
import sys
import os

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()
NEWS = open(os.path.join(here, 'NEWS.txt')).read()


version = '0.2.9b3'

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
      package_dir={'': 'src'}, include_package_data=True,
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
