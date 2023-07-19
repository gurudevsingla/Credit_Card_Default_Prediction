import shutil
import sqlite3
from datetime import datetime
from os import listdir
import os
import csv
from application_logging.logger import App_Logger
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
import json

class dBOperation:
    """
          This class shall be used for handling all the SQL operations.

          Written By: iNeuron Intelligence
          Version: 1.0
          Revisions: None

          """

    def __init__(self):
        self.secure_connect_bundle_path = 'Database_File/secure-connect-test.zip'
        self.badFilePath = "Prediction_Raw_Files_Validated/Bad_Raw"
        self.goodFilePath = "Prediction_Raw_Files_Validated/Good_Raw"
        self.db_columns_path = "prediction_columns_dbwise.json"
        self.logger = App_Logger()


    def dataBaseConnection(self,DatabaseName):

        """
                        Method Name: dataBaseConnection
                        Description: This method creates the database with the given name and if Database already exists then opens the connection to the DB.
                        Output: Connection to the DB
                        On Failure: Raise ConnectionError

                         Written By: iNeuron Intelligence
                        Version: 1.0
                        Revisions: None

                        """
        try:
            cloud_config = {
                'secure_connect_bundle': self.secure_connect_bundle_path
            }
            auth_provider = PlainTextAuthProvider('ZEfJzkwqPPeziFqkdknYPrzz','C436E_yP1Kctp4Pytp29jpFb2WZWGZZcT.aF_jeODHlGfS6b7pwAIeWZfHjesweRGoQP81BTM_pbAiASU,ByAdagCWbq_fes0nWABJoQn_pQ-2opITi+oANdKyO1Goyi')
            cluster = Cluster(cloud=cloud_config, auth_provider=auth_provider)
            session = cluster.connect('gurudev')

            session.default_timeout = 60
            row = session.execute("select release_version from system.local").one()
            if row:
                file = open("Training_Logs/DataBaseConnectionLog.txt", 'a+')
                self.logger.log(file, "Opened {db} database successfully {version}".format(db = DatabaseName,version = str(row[0])))
                file.close()
            else:
                file = open("Training_Logs/DataBaseConnectionLog.txt", 'a+')
                self.logger.log(file, "Error while connecting to database: %s" % ConnectionError)
                file.close()
        except Exception as e:
            file = open("Training_Logs/DataBaseConnectionLog.txt", 'a+')
            self.logger.log(file, "Error while connecting to database: %s" % e)
            file.close()
            raise e
        return session

    def createTableDb(self,DatabaseName,column_names):

        """
           Method Name: createTableDb
           Description: This method creates a table in the given database which will be used to insert the Good data after raw data validation.
           Output: None
           On Failure: Raise Exception

            Written By: iNeuron Intelligence
           Version: 1.0
           Revisions: None

        """
        try:
            session = self.dataBaseConnection(DatabaseName)
            session.execute('DROP TABLE IF EXISTS Good_Raw_Pred_Data').one()

            for key in column_names.keys():
                type = column_names[key]

                # we will remove the column of string datatype before loading as it is not needed for training
                #in try block we check if the table exists, if yes then add columns to the table
                # else in catch block we create the table
                try:
                    session.execute('ALTER TABLE Good_Raw_Pred_Data ADD {column_name} {dataType}'.format(column_name=key.replace('.','_'),dataType=type)).one()
                except:
                    session.execute('CREATE TABLE IF NOT EXISTS Good_Raw_Pred_Data ({column_name} {dataType} primary key)'.format(column_name=key, dataType=type))

            session.shutdown()

            file = open("Prediction_Logs/DbTableCreateLog.txt", 'a+')
            self.logger.log(file, "Tables created successfully!!")
            file.close()

            file = open("Prediction_Logs/DataBaseConnectionLog.txt", 'a+')
            self.logger.log(file, "Closed %s database successfully" % DatabaseName)
            file.close()

        except Exception as e:
            file = open("Prediction_Logs/DbTableCreateLog.txt", 'a+')
            self.logger.log(file, "Error while creating table: %s " % e)
            file.close()
            session.shutdown()
            file = open("Prediction_Logs/DataBaseConnectionLog.txt", 'a+')
            self.logger.log(file, "Closed %s database successfully" % DatabaseName)
            file.close()
            raise e


    def insertIntoTableGoodData(self, Database, column_names):

        """
                                       Method Name: insertIntoTableGoodData
                                       Description: This method inserts the Good data files from the Good_Raw folder into the
                                                    above created table.
                                       Output: None
                                       On Failure: Raise Exception

                                        Written By: iNeuron Intelligence
                                       Version: 1.0
                                       Revisions: None

                """

        session = self.dataBaseConnection(Database)
        goodFilePath= self.goodFilePath
        badFilePath = self.badFilePath
        onlyfiles =  listdir(goodFilePath)
        columns_list = list(column_names.keys())
        log_file = open("Prediction_Logs/DbInsertLog.txt", 'a+')

        for file in onlyfiles:
            try:
                with open(goodFilePath+'/'+file, "r") as f:
                    next(f)
                    reader = csv.reader(f, delimiter="\n")
                    for line in enumerate(reader):
                        for list_ in (line[1]):
                            try:
                                session.execute('INSERT INTO Good_Raw_Pred_Data ({attributes}) values ({values})'.format(attributes = (", ".join(columns_list).replace('.','_')),values=(list_))).one()
                                self.logger.log(log_file," %s: File loaded successfully!!" % file)
                            except Exception as e:
                                raise e

            except Exception as e:

                self.logger.log(log_file,"Error while creating table: %s " % e)
                shutil.move(goodFilePath+'/' + file, badFilePath)
                self.logger.log(log_file, "File Moved Successfully %s" % file)
                log_file.close()
                session.shutdown()
                raise e

        session.shutdown()
        log_file.close()


    def selectingDatafromtableintocsv(self, Database):

        """
                                       Method Name: selectingDatafromtableintocsv
                                       Description: This method exports the data in GoodData table as a CSV file. in a given location.
                                                    above created .
                                       Output: None
                                       On Failure: Raise Exception

                                        Written By: iNeuron Intelligence
                                       Version: 1.0
                                       Revisions: None

                """

        self.fileFromDb = 'Prediction_FileFromDB/'
        self.fileName = 'InputFile.csv'
        log_file = open("Prediction_Logs/ExportToCsv.txt", 'a+')
        # we have columns in unsorted manner but when we are fetching them from database then attributes arrange
        # themselves in sorted manner so we are loading json file which have sorted columns name.
        try:
            with open(self.db_columns_path, 'r') as f:
                dic=json.load(f)
                f.close()
                column_names = dic['ColName']
            session = self.dataBaseConnection(Database)
            session = self.dataBaseConnection(Database)
            cassandraSelect = "SELECT *  FROM Good_Raw_Pred_Data"
            row = session.execute(cassandraSelect)

            results = row.all()

            #Get the headers of the csv file
            headers = list(column_names.keys())

            #Make the CSV ouput directory
            if not os.path.isdir(self.fileFromDb):
                os.makedirs(self.fileFromDb)

            # Open CSV file for writing.
            csvFile = csv.writer(open(self.fileFromDb + self.fileName, 'w', newline=''),delimiter=',', lineterminator='\r\n',quoting=csv.QUOTE_ALL, escapechar='\\')

            # Add the headers and data to the CSV file.
            csvFile.writerow(headers)
            for row in results:
                csvFile.writerow(row)

            self.logger.log(log_file, "File exported successfully!!!")
        except Exception as e:
            self.logger.log(log_file, "File exporting failed. Error : %s" %e)
            raise e





