import os

class Config:
    def get_db_config(self):
        return {
            "host": "localhost",
            "user": "root",
            "password": "",
            "database": "ascel"
        }

config = Config()
