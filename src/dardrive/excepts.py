#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#2012, jfardello@uoc.edu


class DardriveException(Exception): pass

class CatalogException(DardriveException): pass

class BackupException(DardriveException): pass

class RecoverException(BackupException): pass

class BackupDBException(BackupException): pass

class ImporterExeption(DardriveException): pass

class RefCatalogError(CatalogException): pass

class ConfigException(Exception): pass

class ConfigValidationException(ConfigException): pass

class ConfigPasswdException(ConfigValidationException): pass

class ConfigSectionException(ConfigException): pass

class ConfigFileException(ConfigValidationException, IOError): pass

class InitException(ConfigException): pass

class LockException(BackupException): pass

class ParException(DardriveException): pass

class XattrException(DardriveException): pass

class RecoverError(DardriveException): pass
