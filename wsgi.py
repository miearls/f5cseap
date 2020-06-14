from flask import (Flask, request)
from flask_restful import (Api, Resource)
from flasgger import Swagger
from LogStream import f5cloudservices
import logging

application = Flask(__name__)
application.config['SWAGGER'] = {
    'title': 'CS EAP LogStream F5',
    'openapi': '3.0.2'
}
api = Api(application)
swagger = Swagger(application)


def setup_logging(log_level, log_file):
    if log_level == 'debug':
        log_level = logging.DEBUG
    elif log_level == 'verbose':
        log_level = logging.INFO
    else:
        log_level = logging.WARNING

    logging.basicConfig(filename=log_file, format='%(asctime)s %(levelname)s %(message)s', level=log_level)
    return logging.getLogger(__name__)


# Logging settings
global logger
logger = None

global f5cs_subscription
f5cs = None


@swagger.definition('system', tags=['v2_model'])
class ConfigSystem:
    """
    Recommendation Query Context
    ---
    required:
      - log
    properties:
        log:
          type: object
          schema:
          $ref: '#/definitions/system_log'
    """

    @staticmethod
    def prepare(data_json):
        if 'log' in data_json.keys():
            result = ConfigSystemLog.prepare(data_json['log'])
            return {
                'code': result['code'],
                'log': result
            }
        else:
            return None

    @staticmethod
    def set(data_json):
        ConfigSystemLog.set(data_json['log'])

    @staticmethod
    def get():
        return ConfigSystemLog.get()


@swagger.definition('system_log', tags=['v2_model'])
class ConfigSystemLog:
    """
    Recommendation Query Context
    ---
    required:
      - log_level
      - log_file
    properties:
      log_level:
        type: string
        description: log level
      log_file:
        type: string
        description: absolute or relative log file path
    """

    @staticmethod
    def prepare(data_json):
        if 'log_level' in data_json and 'log_file' in data_json:
            result = {
                'code': 200,
                'object': setup_logging(
                    log_level=data_json['log_level'],
                    log_file=data_json['log_file']
                )
            }
        else:
            result = {
                'code': 400,
                'msg': 'parameters: log_level, log_file must be set'
            }
        return result

    @staticmethod
    def set(data_json):
        logger = data_json['object']

    @staticmethod
    def get():
        if logger is not None:
            return {
                'log_level': logger.getLevelName()
            }
        else:
            return None


@swagger.definition('f5cs', tags=['v2_model'])
class ConfigF5CS:
    """
    Recommendation Query Context
    ---
    required:
      - username
      - password
    properties:
      username:
        type: string
        description: F5 CS user account
      password:
        type: string
        description: password
    """

    @staticmethod
    def prepare(data_json):
        if 'username' in data_json and 'password' in data_json:

            # no change
            if f5cs is not None and 'username' == f5cs.username:
                result = {
                    'code': 202,
                    'object': f5cs
                }

            # change
            else:
                result = {
                    'code': 200,
                    'object': f5cloudservices.F5CSEAP(
                        username=data_json['username'],
                        password=data_json['password'],
                        logger=None
                    )
                }
        else:
            result = {
                'code': 400,
                'msg': 'parameters: username, password must be set'
            }
        return result

    @staticmethod
    def set(data_json):
        f5cs = data_json['object']
        f5cs.enable(logger)
        f5cs.fecth_subscriptions()

    @staticmethod
    def get():
        if f5cs is not None:
            return {
                'username': f5cs.username
            }
        else:
            return None


class Declare(Resource):
    def get(self):
        return {
            'system': ConfigSystem.get(),
            'f5cs': ConfigF5CS.get()
        }, 200

    def post(self):
        """
        Configure LogStream in one declaration
        ---
        tags:
          - f5
        consumes:
          - application/json
        parameters:
          - in: body
            name: body
            schema:
              required:
                - system
                - f5cs
              properties:
                system:
                  type: object
                  schema:
                  $ref: '#/definitions/system'
                f5cs:
                  type: object
                  schema:
                  $ref: '#/definitions/f5cs'
        responses:
          200:
            description: Deployment done
         """
        data_json = request.get_json()
        result = {}

        # Sanity check
        cur_class = 'system'
        if cur_class in data_json.keys():
            result[cur_class] = ConfigSystem.prepare(data_json[cur_class])
            if result[cur_class]['code'] not in (200, 201, 202):
                return result, result[cur_class]['code']
        else:
            return {
                'code': 400,
                'msg': 'parameters: ' + cur_class + ' must be set'
            }

        cur_class = 'f5cs'
        if cur_class in data_json.keys():
            result[cur_class] = ConfigF5CS.prepare(data_json[cur_class])
            if result[cur_class]['code'] not in (200, 201, 202):
                return result, result[cur_class]['code']
        else:
            return {
                'code': 400,
                'msg': 'parameters: ' + cur_class + ' must be set'
            }

        # Deploy
        cur_class = 'system'
        if cur_class in data_json.keys():
            ConfigSystem.set(result[cur_class])

        cur_class = 'f5cs'
        if cur_class in data_json.keys():
            ConfigF5CS.set(result[cur_class])

        return result, 200


api.add_resource(Declare, '/declare')

# Start program
if __name__ == '__main__':
    print("Dev Portal: http://127.0.0.1:5000/apidocs/")
    application.run(
        host="0.0.0.0",
        debug=True,
        use_reloader=True,
        port=5000
    )
