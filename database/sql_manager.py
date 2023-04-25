from PyQt6.QtCore import QRunnable, pyqtSignal, QObject
from math import sin, cos, sqrt, atan2, radians
from mariadb import Cursor
import mariadb

from database.mwlink_model import MwLink


class SqlManager:
    # Do not spam log with error messages
    is_error_sent = False

    def __init__(self, config_man):
        super(SqlManager, self).__init__()
        # Load settings from config file via ConfigurationManager
        self.settings = config_man.load_sql_config()
        # Init empty connections
        self.connection_metadata = None
        self.connection_output = None
        # Define connection state
        self.is_connected = False

    def connect(self):
        try:
            self.connection_metadata = mariadb.connect(
                user=self.settings['user'],
                password=self.settings['pass'],
                host=self.settings['address'],
                port=int(self.settings['port']),
                database=self.settings['db_metadata'],
                connect_timeout=int(int(self.settings['timeout'])/1000),
                reconnect=True
            )

            self.connection_output = mariadb.connect(
                user=self.settings['user'],
                password=self.settings['pass'],
                host=self.settings['address'],
                port=int(self.settings['port']),
                database=self.settings['db_output'],
                connect_timeout=int(int(self.settings['timeout'])/1000),
                reconnect=True
            )

            self.is_connected = True
            SqlManager.is_error_sent = False

        except mariadb.Error as e:
            if not SqlManager.is_error_sent:
                print(f"Cannot connect to MariaDB Platform: {e}")
                SqlManager.is_error_sent = True
            self.is_connected = False

    def check_connection(self) -> bool:
        if self.is_connected:
            try:
                self.connection_metadata.ping()
                self.connection_output.ping()
                return True
            except mariadb.InterfaceError:
                return False
        else:
            self.connect()
            return self.is_connected

    def load_metadata(self) -> dict:
        try:
            if self.check_connection():
                cursor: Cursor = self.connection_metadata.cursor()

                query = "SELECT links.ID, links.IP_address_A, links.IP_address_B, links.technology, " \
                        "links.frequency_A, links.frequency_B, links.polarization, "\
                        "sites_A.address AS address_A, "\
                        "sites_B.address AS address_B, "\
                        "sites_A.X_coordinate AS longitude_A, "\
                        "sites_B.X_coordinate AS longitude_B, "\
                        "sites_A.Y_coordinate AS latitude_A, "\
                        "sites_B.Y_coordinate AS latitude_B, "\
                        "sites_A.X_dummy_coordinate AS dummy_longitude_A, "\
                        "sites_B.X_dummy_coordinate AS dummy_longitude_B, "\
                        "sites_A.Y_dummy_coordinate AS dummy_latitude_A, "\
                        "sites_B.Y_dummy_coordinate AS dummy_latitude_B "\
                        "FROM links "\
                        "JOIN sites AS sites_A ON links.site_A = sites_A.ID "\
                        "JOIN sites AS sites_B ON links.site_B = sites_B.ID;"

                cursor.execute(query)

                links = {}

                for (ID, IP_address_A, IP_address_B, technology, frequency_A, frequency_B, polarization,
                     address_A, address_B, longitude_A, longitude_B, latitude_A, latitude_B,
                     dummy_longitude_A, dummy_longitude_B, dummy_latitude_A, dummy_latitude_B) in cursor:

                    link_length = calc_distance(latitude_A, longitude_A, latitude_B, longitude_B)
                    link = MwLink(ID, address_A + ' <--> ' + address_B, technology, address_A, address_B, frequency_A,
                                  frequency_B, polarization, IP_address_A, IP_address_B, link_length,
                                  latitude_A, longitude_A, latitude_B, longitude_B,
                                  dummy_latitude_A, dummy_longitude_A, dummy_latitude_B, dummy_longitude_B)
                    links[ID] = link

                return links
            else:
                raise mariadb.Error('Connection is not active.')
        except mariadb.Error as e:
            # TODO: exception handling
            print(f"Failed to read data from MariaDB: {e}")
            return {}


class SqlChecker(SqlManager, QRunnable):
    # subclass for use in threadpool, for connection testing
    # emits 'ping_signal' from 'SqlSignal' class passed as 'signals' parameter
    def __init__(self, config_man, signals: QObject):
        super(SqlChecker, self).__init__(config_man)
        self.sig = signals

    def run(self):
        self.sig.ping_signal.emit(self.check_connection())


class SqlSignals(QObject):
    # signaling class for SqlManager's threadpool subclasses
    ping_signal = pyqtSignal(bool)


def calc_distance(lat_A, long_A, lat_B, long_B) -> float:
    # Approximate radius of earth in km
    r = 6373.0

    lat_A = radians(lat_A)
    long_A = radians(long_A)
    lat_B = radians(lat_B)
    long_B = radians(long_B)

    dlon = long_B - long_A
    dlat = lat_B - lat_A

    a = sin(dlat / 2) ** 2 + cos(lat_A) * cos(lat_B) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return r * c
