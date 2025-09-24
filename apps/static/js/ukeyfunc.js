function zaykPlugin() {


    SUCCESS = 0;
    COMMON_ERROR = -1;
    RECEIVE_ERROR = -2;
    SEND_ERROR = -3;


    var _xmlhttp;

    function AjaxIO(json_in) {

        var _url = "http://127.0.0.1:13555?" + json_in;
        if (_xmlhttp == null) {
            if (window.XMLHttpRequest) { // code for IE7+, Firefox, Chrome, Opera, Safari
                _xmlhttp = new XMLHttpRequest();
            } else { // code for IE6, IE5
                _xmlhttp = new ActiveXObject("Microsoft.XMLHTTP");
            }
        }
        _xmlhttp.open("GET", _url, false);
        _xmlhttp.send(null);

    };


    function GetHttpResult() {

        if (_xmlhttp.readyState == 4 && _xmlhttp.status == 200) {

            var retObj = eval("(" + _xmlhttp.responseText + ")");

            return retObj;
        } else {
            return null;
        }
    }

    // 断开连接
    this.SOF_DeviceDisConnect = function() {

        var json = '{"CMD": 0,"params":  {}}';

        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return SUCCESS;
        } else {
            return ret;
        }
    };

    // 连接
    this.SOF_DeviceConnect = function() {

        var json = '{"CMD": 1,"params":  {}}';

        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return SUCCESS;
        } else {
            return ret;
        }

    };


    // 获取ukey数量
    this.SOF_GetUKeyNumber = function() {

        var json = '{"CMD": 2,"params":  {}}';

        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return SUCCESS;
        } else {
            return ret.count;
        }
    };

    // 获取ukey句柄
    this.SOF_GetKeyName = function() {

        var json = '{"CMD": 3,"params":  {"index": 1}}';

        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            // return SUCCESS;
            return ret.params;
        } else {
            return ret;
        }

        return COMMON_ERROR;
    };

    //SM2数据签名
    this.SOF_SM2Sign = function(keyName, data, isBase) {
        var json = '{"CMD": 55,"params":  {"keyName": "' + keyName + '","isBase":"' + isBase + '","data":"' + data + '"}}';
        console.log(json)
        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return ret.params;
        } else {
            return ret.errcode;
        }
    };

    // 获取签名公钥
    this.SOF_GetSignPubkey = function(keyName) {
        var json = '{"CMD": 52,"params":{"keyName":"' + keyName + '"}}';
        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();

        if (ret.errcode == 0) {
            return ret.params;
        } else {
            return ret.errcode;
        }
    };

    //导入证书
    this.SOF_ImportSignCert = function(keyName, base64Cert) {
        var json = '{"CMD": 54,"params":{"keyName":"' + keyName + '","base64Cert":"' + base64Cert + '"}}';
        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return SUCCESS;
        } else {
            return ret.errcode;
        }
    };

    // 获取ukey状态
    this.SOF_GetUkeyStatus = function(keyName) {
        var json = '{"CMD": 4,"params":{"keyName":"' + keyName + '"}}';
        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (!ret) {
            return null
        }
        if (ret.errcode == 0) {
            return SUCCESS;
        } else {
            return ret.errcode;
        }
    };

    // 获取ukey制造商信息
    this.SOF_GetUkeyMakerData = function(keyName) {
        var json = '{"CMD": 10,"params":{"keyName":"' + keyName + '"}}';
        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return ret.params;
        } else {
            return ret.errcode;
        }
    };


    // 获取ukey标签信息
    this.SOF_GetUkeyTagData = function(keyName) {
        var json = '{"CMD": 11,"params":{"keyName":"' + keyName + '"}}';
        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return ret.params;
        } else {
            return ret.errcode;
        }
    };

    // 获取ukey序列号
    this.SOF_GetUkeySerialNum = function(keyName) {
        var json = '{"CMD": 12,"params":{"keyName":"' + keyName + '"}}';
        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return ret.params;
        } else {
            return ret.errcode;
        }
    };

    // 获取ukey状态码
    this.SOF_GetUkeyStatusCode = function(keyName) {
        var json = '{"CMD": 13,"params": {"keyName":"' + keyName + '"}}';
        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return ret.params;
        } else {
            return ret.errcode;
        }
    };

    // 初始化
    this.SOF_InitUkey = function(keyName, appName, containerName, userPin) {
        var json = '{"CMD": 20,"params":  {"keyName": "' + keyName + '","appName":" ' + appName + ' ","containerName" :"' + containerName + '","userPin":"' + userPin + '"}}';
        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return SUCCESS;
        } else {
            return ret.errcode;
        }
    };
    this.SOF_EnumApp = function(keyName) {
        var json = '{"CMD": 30,"params":{"keyName":"' + keyName + '"}}';

        try {
            AjaxIO(json);
        } catch (e) {
            return this.SEND_ERROR;
        }

        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return ret.params;
        } else {
            return ret.errcode;
        }
    };


    //2.13.1 打开应用
    this.SOF_OpenApp = function(keyName, appName, pin) {
        var json = '{"CMD": 22,"params":  {"keyName": "' + keyName + '","appName": "' + appName + '","userPin": "' + pin + '"}}';

        try {
            AjaxIO(json);
        } catch (e) {
            return this.SEND_ERROR;
        }

        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return this.SUCCESS;
        } else {
            return ret;
        }
    };

    //2.15.	枚举容器
    this.SOF_EnumCont = function(keyName) {
        var json = '{"CMD": 31,"params":{"keyName":"' + keyName + '"}}';

        try {
            AjaxIO(json);
        } catch (e) {
            return this.SEND_ERROR;
        }

        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return ret.params;
        } else {
            return ret.errcode;
        }
    };
    // 打开和应用容器
    this.SOF_OpenApplyAndContainer = function(keyName, appName, containerName, userPin) {

        appName = this.SOF_EnumApp(keyName);
        this.SOF_OpenApp(keyName, appName, userPin)
        containerName = this.SOF_EnumCont(keyName)
        var json = '{"CMD": 21,"params":  {"keyName": "' + keyName + '","appName":" ' + appName + ' ","containerName" :"' + containerName + '","userPin":"' + userPin + '"}}';
        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();

        if (ret.errcode == 0) {
            return SUCCESS;
        } else {
            return ret;
        }
    };

    // 关闭和应用容器
    this.SOF_ShutApplyAndContainer = function(keyName) {
        var json = '{"CMD": 26,"params":  {"keyName": "' + keyName + '"}}';
        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return SUCCESS;
        } else {
            return ret;
        }
    };

    // 修改ukey口令
    this.SOF_UpdateUkeyPin = function(keyName, oldPin, newPin) {
        var json = '{"CMD": 27,"params":  {"keyName": "' + keyName + '","oldPin": "' + oldPin + '","newPin":"' + newPin + '"}}';
        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return SUCCESS;
        } else {
            return ret.errcode;
        }
    };

    // 生成RSA签名密钥对
    this.SOF_CreateRSA = function(keyName, signKeyLen) {

        var json = '{"CMD": 80,"params":  {"keyName": "' + keyName + '","signKeyLen":' + signKeyLen + '}}';

        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();

        if (ret.errcode == 0) {
            return ret.params;
        } else {
            return ret.errcode;
        }
    };

    // 导出RSA签名公钥
    this.SOF_GetRSASignPubkey = function(keyName) {

        var json = '{"CMD": 82,"params": {"keyName":"' + keyName + '"}}';

        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        console.log(ret)

        if (ret.errcode == 0) {
            // return SUCCESS;
            return ret.params;
        } else {
            return ret.errcode;
        }
    };

    // 生成SM2密钥对
    this.SOF_CreateSM2 = function(keyName) {
        var json = '{"CMD": 50,"params":  {"keyName": "' + keyName + '"}}';
        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return ret.params;
        } else {
            return ret.errcode;
        }

    };

    //生成P10请求
    this.SOF_CreateP10 = function(keyName, CN) {
        //var json = '{"CMD": 65,"params": {"keyName" : "' + keyName + '","CN":"' + CN  + '","OU": "' + OU + '","Email":"' + Email + '","O":"' + O + '","ST":"'+ ST +'","L":"' + L +'","keyType":"' + keyType + '"}}';
        var json = '{"CMD": 65,"params":{"keyName":"' + keyName + '","CN":"' + CN + '"}}';
        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return ret.params;
        } else {
            return ret.errcode;
        }
    };

    // 写入数据
    this.SOF_DataWrite = function(keyName, fileName, data) {
        var json = '{"CMD":40,"params": {"keyName": "' + keyName + '","fileName": "' + fileName + '","data":"' + data + '"}}';
        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return SUCCESS;
        } else {
            return ret.errcode;
        }
    };

    // 读取数据
    this.SOF_DataRead = function(keyName, maxLength) {
        var json = '{"CMD":41,"params": {"keyName":"' + keyName + '","maxLength": ' + maxLength + '}}';
        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return ret.params;
        } else {
            return ret.errcode;
        }
    };

    //生成签名密钥
    this.SOF_SignSecretKey = function(keyName, keyType) {
        var map = {};
        map.CMD = 60;
        map.params = {};
        map.params.keyName = keyName;
        map.params.keyType = keyType;
        try {
            AjaxIO(JSON.stringify(map));
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return ret.params.split(':')[1];
        } else {
            return ret.errcode;
        }
    };

    // 导入证书和密钥
    this.SOF_ImportCertAndKey = function(keyName, keyType, CertAndKey) {
        var map = {};
        map.CMD = 61;
        map.params = {};
        map.params.keyName = keyName;
        map.params.keyType = keyType;
        map.params.CertAndKey = CertAndKey;
        try {
            AjaxIO(JSON.stringify(map));
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return SUCCESS;
        } else {
            return ret.errcode;
        }
    };

    // 导出签名证书
    this.SOF_UploadSignCert = function SOF_UploadSignCert(keyName) {
        var json = '{"CMD": 62,"params": {"keyName":"' + keyName + '"}}';
        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return ret.params;
        } else {
            return ret.errcode;
        }
    };

    // 获取证书CN项和序列号
    this.SOF_GetCertCNAndSerial = function SOF_GetCertCNAndSerial(keyName) {
        var json = '{"CMD": 63,"params": {"keyName":"' + keyName + '"}}';
        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return ret.params;
        } else {
            return ret.errcode;
        }
    };



    // 验证ukey口令
    this.SOF_VerifyUkeyPass = function SOF_VerifyUkeyPass(keyName, pin) {
        var json = '{"CMD": 28,"params": {"keyName": "' + keyName + '","pin": "' + pin + '"}}';
        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return SUCCESS;
        } else {
            return ret;
        }
    };

    //生成证书
    this.SOF_CreateImportCert = function(keyName, rootCert, priKey, cnUser, ouDept, oOrg, sPro, lLocal) {
        var json = '{"CMD": 64,"params": {"keyName": "' + keyName + '","rootCert": "' + rootCert + '","priKey": "' + priKey + '","cnUser": "' + cnUser + '","ouDept": "' + ouDept + '","oOrg": "' + oOrg + '","sPro": "' + sPro + '","lLocal": "' + lLocal + '"}}';
        try {
            AjaxIO(json);
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return SUCCESS;
        } else {
            return ret;
        }
    };
    // 导入RSA签名或加密证书
    this.SOF_ImpCertByRSA = function(keyName, certType, base64Cert) {
        var map = {};
        map.CMD = 84;
        map.params = {};
        map.params.keyName = keyName;
        map.params.certType = certType;
        map.params.base64Cert = base64Cert;
        try {
            AjaxIO(JSON.stringify(map));
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return SUCCESS;
        } else {
            return ret;
        }
    };

    // 导入RSA加密密钥
    this.SOF_ImpEncKeyByRSA = function(keyName, keyPair) {
        var map = {};
        map.CMD = 89;
        map.params = {};
        map.params.keyName = keyName;
        map.params.keyPair = keyPair;
        try {
            AjaxIO(JSON.stringify(map));
        } catch (e) {
            return SEND_ERROR;
        }
        var ret = GetHttpResult();
        if (ret.errcode == 0) {
            return SUCCESS;
        } else {
            return ret;
        }
    };
}