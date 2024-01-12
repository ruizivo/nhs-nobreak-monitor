import telnetlib
import sys
import time
import re
import json
import os
import traceback
import paho.mqtt.client as mqtt

debug = True
localTest= False

class Mqtt:
    def __init__(self, host, port, clientName, user="", password=""):

        self.host = host
        self.port = port
        self.user = user
        self.password = password

        self.client = mqtt.Client(clientName)

        if self.user and self.password:
            self.client.username_pw_set(self.user, self.password)

    def publish(self, topic, payload, retain=False):
        self.client.publish(topic, payload=payload, retain=retain)

    def willSet(self, topic, payload, retain=False):
        self.client.will_set(topic, payload=payload, retain=retain)

    def stop(self):
        self.client.loop_stop()

    def start(self):
        try:
            self.client.connect(self.host, self.port)
            self.client.loop_start()
        except Exception as e:
            print(e)
            traceback.print_exc()
            sys.exit()

class Telnet:
    def __init__(self, host, port, username, password) -> None:
        self.connect(host, port, username, password)
    
    def connect(self, host, port, username, password):
        try:
            self.tn = telnetlib.Telnet(host, port)
            self.tn.read_until(b"Usuario: ")
            self.tn.write(username.encode('ascii') + b"\r\n")
            if password:
                self.tn.read_until(b"Senha:")
                self.tn.write(password.encode('ascii') + b"\r\n")
            
            time.sleep(1)
            self.tn.read_very_eager().decode('ascii') # "clean"
        except Exception as e:
            print("Erro ao realizar a conexao!")
            raise Exception("error")
    
    def isConnected(self):
        return self.tn.sock.fileno()
    
    def executCommand(self, command):
        self.tn.write(command.encode('ascii') + b"\r\n")
        time.sleep(1)
        self.tn.read_until(command.encode('ascii'))
        output = self.tn.read_very_eager().decode('ascii')
        return output.replace(">", "")
    def close(self):
        self.tn.close()

class HomeAssistantDevice:

    discoveryTopic = "homeassistant/{sensorType}/{deviceName}/{sensorName}/config"
    discoveryStateTopic = "{deviceName}/{sensorType}/{sensorName}/state"

    def __init__(self, data, nhsHost, mqttHost, mqttPort, mqttUser, mqttPass) -> None:
        if mqttHost and mqttPort:
            self.nhsHost = nhsHost
            self.mqtt_client = Mqtt(mqttHost, mqttPort, "NHS", mqttUser, mqttPass )            
            self.homeAssistantDiscovery(data)
        else:
            self.mqtt_client = None

    def start(self):
        self.mqtt_client.start()

    def homeAssistantDiscovery(self, data):
        if self.mqtt_client:
            deviceName = data["Identificacao do equipamento"]["Modelo"].replace(" ","")
            self.will(deviceName,"binary_sensor", "Equipamento", "OFF")
            self.start()
            self.createDeviceSensor(deviceName, ["Equipamento", "sim"])
            for key in data["Dados do equipamento"].items():
                self.createDeviceSensor(deviceName, key) 

    def updateStatus(self, status):
        if self.mqtt_client:
            self.mqtt_client.publish(self.stateTopic, status)

    def updateAttributes(self, attr):
        if self.mqtt_client:
            self.mqtt_client.publish(self.attrTopic, attr)

    def getSensorType(self, data):

        if data['Dados do equipamento']['Rede em falha'] == 'sim':
            state = 'OFF'
        elif data['Dados do equipamento']['Rede em falha'] == 'nao':
            state = 'ON'
        else:
            state = 'UNKNOW'

        return(state)
    
    def will(self, deviceName, sensorType, sensorName, value):
        topic = self.discoveryStateTopic.replace("{deviceName}", deviceName).replace("{sensorType}", sensorType).replace("{sensorName}", "NHS_"+ sensorName )
        self.mqtt_client.willSet(topic, value)

    def sendValue(self, deviceName, sensorType, sensorName, value):
        topic = self.discoveryStateTopic.replace("{deviceName}", deviceName).replace("{sensorType}", sensorType).replace("{sensorName}", "NHS_"+ sensorName )
        self.mqtt_client.publish(topic, value)

        if debug:
            print(topic, value)
    
    def sendAllValues(self, data):
        deviceName = data["Identificacao do equipamento"]["Modelo"].replace(" ","")
    
        for key in data["Dados do equipamento"].items():

            sensorType = "sensor"
            if key[1] == "nao":
                sensorType = "binary_sensor"
                valor = "OFF"
            if key[1] == "sim":
                sensorType = "binary_sensor"
                valor = "ON"
            if key[1] == "indefinido":
                sensorType = "binary_sensor"
                valor = "UNKNOW"

            if(sensorType == "sensor"):
                valor, simbolo1 = self.splitNumberAndSymbol(key[1])

            sensorName = key[0].title().replace(" ","")
            self.sendValue(deviceName, sensorType, sensorName, valor)    

        self.sendValue(deviceName, sensorType, "Equipamento", "ON")   


    def createDeviceSensor(self, deviceName, sensorValue):
        if self.mqtt_client:
            sensorType = "sensor"
            if sensorValue[1] == "nao" or sensorValue[1] == "sim" or sensorValue[1] == "indefinido":
                sensorType = "binary_sensor"

            sensor = {}
            sensor["device"] = {}
            sensor["device"]["configuration_url"]="http://"+self.nhsHost+":2001"
            sensor["device"]["model"] = deviceName
            sensor["device"]["name"] = "NHS"
            sensor["device"]["identifiers"] = [deviceName]
            sensor["device"]["manufacturer"] = "NHS – Nobreaks"
            sensor["unique_id"] = "NHS_"+ sensorValue[0].title().replace(" ","")
            sensor["state_topic"] = self.discoveryStateTopic.replace("{deviceName}", deviceName).replace("{sensorType}", sensorType).replace("{sensorName}", sensor["unique_id"] )
            sensor["name"] = sensorValue[0]

            if sensorType == "sensor":
                numero1, simbolo1 = self.splitNumberAndSymbol(sensorValue[1])
                if simbolo1 == "C":
                    simbolo1 = "°C"
                sensor["unit_of_measurement"] = simbolo1
            # else:
            #     sensor["value_template"] = "{{ value_json.temperature}}",

            topic = self.discoveryTopic.replace("{deviceName}", deviceName).replace("{sensorType}", sensorType).replace("{sensorName}", sensor["unique_id"] )

            if debug:
                print(topic)
                print(json.dumps(sensor, indent=2))

            self.mqtt_client.publish(topic, json.dumps(sensor), True)

    def splitNumberAndSymbol(self, data):
        match = re.match(r"([0-9.]+)\s*([A-Za-z%]+)", data)

        if match:
            number = float(match.group(1))
            symbol = match.group(2)
            return number, symbol
        else:
            return None, None

class Monitor:
    def __init__(self):
        mqttHost =  str(os.getenv("MQTT_HOST"))
        mqttPort =  int(os.getenv("MQTT_PORT"))
        mqttUser =  str(os.getenv("MQTT_USER"))
        mqttPass =  str(os.getenv("MQTT_PASS"))
        nhsHost =  str(os.getenv("NHS_HOST"))

        try:
            telnetHost = "127.0.0.1"
            telnetUsername = "admin"
            telnetPassword = "admin"
            telnetPort = 2000

            if debug:
                print("Init telnet on ", telnetHost)   

            tn = None
            while (tn == None):
                try:
                    tn = Telnet(telnetHost, telnetPort, telnetUsername, telnetPassword)  
                except Exception as e:  
                    print("tentando conectar")
                    time.sleep(5)      

            if not localTest:
                data = self.getInfo(tn.executCommand("estado"))
            else:
                data = self.getInfo(self.getText())

            if mqttHost:
                if debug:
                    print("----- init homeassistant device -----")
                self.device = HomeAssistantDevice(data, nhsHost, mqttHost, mqttPort, mqttUser, mqttPass )
        
            if debug:
                print("----- init main loop -----")

            while (True):
                if debug:
                    print("----- begin of send -----")
                    
                if not localTest:
                    text = tn.executCommand("estado")
                else:
                    text = self.getText()

                data = self.getInfo(text)
                if mqttHost:
                    self.device.sendAllValues(data)

                if debug:
                    print("----- end of send -----")
                time.sleep(10)
                
        except Exception as e:
            print(e)
            traceback.print_exc()
            sys.exit()

        finally:
            if tn:
                tn.close()
                print("Conection Telnet closed")

    def getText(self):# only for local tests
        return """
Identificacao do equipamento:
                        Modelo: NHS Mini Max
            Versao da placa: 0
        Quantidade de baterias: 1
    Tensao de entrada nominal: 220.0 V
    Tensao de saida nominal: 220.0 V
            Mede temperatura: sim
        Mede tensao de saida: sim
            Tipo de bateria: selada
Mede corrente do carregador: sim

Configuracao do equipamento:
                Valida desde: 04/Jan 20:28:21
            Versao do firmware: 20
                Subtensao 120V: 95.0 V
            Sobretensao 120V: 145.0 V
                Subtensao 220V: 180.0 V
            Sobretensao 220V: 249.0 V
        Tensao nominal 120V: 120.0 V
        Tensao nominal 220V: 220.0 V
        Corrente do carregador: 0 mA

Configuracao do servidor:
                        Porta: /dev/ttyS0

Dados do equipamento:
            Tensao de entrada: 220.0 V
            Tensao de saida: 211.0 V
    Tensao de entrada minima: 220.0 V
    Tensao de entrada maxima: 220.0 V
    Tensao nominal de entrada: 220.0 V
    Tensao nominal de saida: 220.0 V
            Tensao da bateria: 13.6 V
                        Carga: 9.0%
                Temperatura: 43 C
        Corrente do carregador: 0 mA
            Potencia excessiva: nao
                Modo inversor: nao
                Bateria baixa: nao
                Rede em falha: nao
        Queda abrupta de rede: nao
                Bypass ativo: sim
            Carregador ativo: nao
"""


    def getInfo(self, text):

        sections = re.split(r'\r\n\r\n+', text.strip())
        # sections = re.split(r'\n\n+', text.strip())

        # Convert into dictionary
        data = {}
        for section in sections:
            # rows = section.split('\n')
            rows = section.split('\r\n')
            category = rows[0].strip(':')
            data[category] = {}
            for linha in rows[1:]:
                key, value = linha.split(':', 1)
                data[category][key.strip()] = value.strip()

        # Convert to JSON
        jsonResult = json.dumps(data, indent=4)

        # print the result
        if debug:
            print(jsonResult)     
        return data   

    

if __name__ == "__main__":
    teste = Monitor()
