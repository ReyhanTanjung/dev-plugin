PLUGIN_NAME=		devicemonitor
PLUGIN_VERSION=		1.0
PLUGIN_REVISION=	1
PLUGIN_COMMENT=		Device telemetry monitoring plugin
PLUGIN_MAINTAINER=	reyhan@tritronik.com

RUN_DEPENDS=		${PYTHON_PKGNAMEPREFIX}psutil>0:sysutils/py-psutil@${PY_FLAVOR} \
			${PYTHON_PKGNAMEPREFIX}requests>0:www/py-requests@${PY_FLAVOR}

.include "../../Mk/plugins.mk"