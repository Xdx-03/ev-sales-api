pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20', artifactNumToKeepStr: '10'))
    }

    parameters {
        choice(
            name: 'TEST_ENV',
            choices: ['test', 'staging'],
            description: '选择 Jenkins 中已经维护好的隔离测试环境'
        )
        choice(
            name: 'TEST_SUITE',
            choices: [
                'safe-regression',
                'smoke',
                'critical-safe',
                'destructive',
                'database'
            ],
            description: '选择测试范围；写数据和数据库套件仍受独立开关保护'
        )
        booleanParam(
            name: 'RUN_LIVE_TESTS',
            defaultValue: false,
            description: '显式开启真实 API 回归；关闭时只执行静态检查和场景收集'
        )
        booleanParam(
            name: 'ALLOW_DESTRUCTIVE',
            defaultValue: false,
            description: '仅在 test 环境允许执行预计创建或修改业务数据的场景'
        )
        booleanParam(
            name: 'ALLOW_DATABASE_CHECKS',
            defaultValue: false,
            description: '允许使用经过权限校验的 SELECT-only 数据库账号执行辅助校验'
        )
        booleanParam(
            name: 'SEND_FEISHU',
            defaultValue: false,
            description: '使用所选 Secret File 中的 Webhook 发送脱敏结果摘要'
        )
    }

    environment {
        PYTHONUNBUFFERED = '1'
        PYTHONUTF8 = '1'
        PIP_DISABLE_PIP_VERSION_CHECK = '1'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install') {
            steps {
                script {
                    if (isUnix()) {
                        sh '''
                            python3 -m venv .venv
                            .venv/bin/python -m pip install -r requirements-dev.txt
                        '''
                    } else {
                        bat '''
                            @echo off
                            python -m venv .venv
                            .venv/Scripts/python.exe -m pip install -r requirements-dev.txt
                        '''
                    }
                }
            }
        }

        stage('Static validation') {
            steps {
                script {
                    if (isUnix()) {
                        sh '''
                            .venv/bin/python -m ruff format --check .
                            .venv/bin/python -m ruff check .
                            .venv/bin/python -m compileall -q ev_api tests scripts run_api_tests.py
                            bash -n scripts/check_linux_test_env.sh
                            .venv/bin/python scripts/validate_postman_assets.py
                            .venv/bin/python -m pytest --collect-only -q
                            .venv/bin/python -m pytest --collect-only -q -m "not destructive and not database"
                        '''
                    } else {
                        bat '''
                            @echo off
                            .venv/Scripts/python.exe -m ruff format --check .
                            .venv/Scripts/python.exe -m ruff check .
                            .venv/Scripts/python.exe -m compileall -q ev_api tests scripts run_api_tests.py
                            .venv/Scripts/python.exe scripts/validate_postman_assets.py
                            .venv/Scripts/python.exe -m pytest --collect-only -q
                            .venv/Scripts/python.exe -m pytest --collect-only -q -m "not destructive and not database"
                        '''
                    }
                }
            }
        }

        stage('Live API regression') {
            when {
                expression { params.RUN_LIVE_TESTS }
            }
            steps {
                script {
                    def configCredentialIds = [
                        test: 'ev-sales-api-test-config',
                        staging: 'ev-sales-api-staging-config'
                    ]
                    def suites = [
                        'safe-regression': [
                            marker: 'not destructive and not database',
                            extraArgs: ''
                        ],
                        smoke: [
                            marker: 'smoke and not destructive and not database',
                            extraArgs: ''
                        ],
                        'critical-safe': [
                            marker: 'critical and not destructive and not database',
                            extraArgs: ''
                        ],
                        destructive: [
                            marker: 'destructive',
                            extraArgs: '--run-destructive'
                        ],
                        database: [
                            marker: 'database',
                            extraArgs: '--run-database-checks'
                        ]
                    ]
                    def credentialId = configCredentialIds[params.TEST_ENV]
                    def suite = suites[params.TEST_SUITE]

                    if (!credentialId || !suite) {
                        error('未知的环境或测试范围参数')
                    }
                    if (params.TEST_SUITE == 'destructive') {
                        if (params.TEST_ENV != 'test') {
                            error('写数据场景只允许在 test 环境执行')
                        }
                        if (!params.ALLOW_DESTRUCTIVE) {
                            error('执行 destructive 套件必须显式开启 ALLOW_DESTRUCTIVE')
                        }
                    }
                    if (params.TEST_SUITE == 'database' && !params.ALLOW_DATABASE_CHECKS) {
                        error('执行 database 套件必须显式开启 ALLOW_DATABASE_CHECKS')
                    }

                    def runnerOptions = [
                        params.SEND_FEISHU ? '' : '--no-feishu',
                        suite.extraArgs
                    ].findAll { it }.join(' ')
                    withCredentials([
                        file(credentialsId: credentialId, variable: 'EV_API_CONFIG_FILE')
                    ]) {
                        if (isUnix()) {
                            sh(
                                label: "Run ${params.TEST_SUITE} on ${params.TEST_ENV}",
                                script: """
                                    set +x
                                    .venv/bin/python run_api_tests.py --config \"\$EV_API_CONFIG_FILE\" --env \"${params.TEST_ENV}\" -m \"${suite.marker}\" ${runnerOptions}
                                """
                            )
                        } else {
                            bat(
                                label: "Run ${params.TEST_SUITE} on ${params.TEST_ENV}",
                                script: """
                                    @echo off
                                    .venv/Scripts/python.exe run_api_tests.py --config \"%EV_API_CONFIG_FILE%\" --env \"${params.TEST_ENV}\" -m \"${suite.marker}\" ${runnerOptions}
                                """
                            )
                        }
                    }
                }
            }
        }
    }

    post {
        always {
            script {
                if (fileExists('reports/junit.xml')) {
                    junit allowEmptyResults: false, testResults: 'reports/junit.xml'
                } else {
                    echo 'JUnit report was not generated; preserving the original stage status.'
                }
                archiveArtifacts(
                    artifacts: 'reports/allure-results/**,reports/junit.xml',
                    allowEmptyArchive: true,
                    fingerprint: false
                )
            }
        }
    }
}
