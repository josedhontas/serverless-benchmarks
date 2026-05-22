
[![Code Linting](https://github.com/spcl/serverless-benchmarks/actions/workflows/lint.yml/badge.svg)](https://github.com/spcl/serverless-benchmarks/actions)
[![Regression](https://github.com/spcl/serverless-benchmarks/actions/workflows/regression.yml/badge.svg)](https://github.com/spcl/serverless-benchmarks/actions)
[![Documentation Status](https://readthedocs.org/projects/sebs/badge/?version=latest)](https://sebs.readthedocs.io/en/latest/?badge=latest)
![Release](https://img.shields.io/github/v/release/spcl/serverless-benchmarks)
![License](https://img.shields.io/github/license/spcl/serverless-benchmarks)
![GitHub issues](https://img.shields.io/github/issues/spcl/serverless-benchmarks)
![GitHub pull requests](https://img.shields.io/github/issues-pr/spcl/serverless-benchmarks)
[![Slack](https://img.shields.io/badge/Slack-Join%20%23serverless--benchmark-purple?logo=Slack)](https://join.slack.com/t/serverlessbenchmark/shared_invite/zt-30622ov74-_S9QeDjAJLZSe9bJC8tStw)

# SeBS: Serverless Benchmark Suite

**FaaS benchmarking suite for serverless functions with automatic build, deployment, and measurements.**

![Overview of SeBS features and components - experiments, platforms we support, and programming languages.](docs/overview.png)

SeBS is a diverse suite of FaaS benchmarks that allows automatic performance analysis of
commercial and open-source serverless platforms. We provide a suite of
[benchmark applications](docs/benchmarks.md) in Python, Node.js, Java, and C++ covering workloads from web applications to scientific computing.
With automtic [experiments](docs/experiments.md), we test and evaluate different components of FaaS systems.
SeBS provides support for **automatic deployment** and invocation of benchmarks on
commercial and black-box platforms
[AWS Lambda](https://aws.amazon.com/lambda/),
[Azure Functions](https://azure.microsoft.com/en-us/services/functions/),
and [Google Cloud Functions](https://cloud.google.com/functions).
Furthermore, we support the open-source platform [OpenWhisk](https://openwhisk.apache.org/)
and [OpenFaaS](https://www.openfaas.com/), and offer a custom, Docker-based local
evaluation platform.

## How can SeBS help you?

* Are you looking for an experimentation platform to test and analyze the performance of serverless across cloud platforms?
* Do you need a set of standardized benchmarks for your serverless experiments and research work?
* Do you want a fully automated pipeline for build, deployment, and measurements, with no manual effort?

Then SeBS might just be the tool for you and your work!

See the [installation instructions](#installation) and [SeBS tutorial](#tutorial) below to learn how to configure SeBS to use selected commercial and open-source serverless systems.
Then, take a look at our documentation to see how SeBS can automatically launch serverless functions and entire experiments in the cloud!
You can also find details about SeBS design and experimental results in [our peer-reviewed publications](#publications).

* [Getting started: how to use SeBS?](docs/usage.md)
* [Getting started: how to configure cloud and serverless platforms?](docs/platforms.md)
* [Going deeper: which benchmark applications are offered?](docs/benchmarks.md)
* [Going deeper: which experiments can be launched to evaluate FaaS platforms?](docs/experiments.md)
* [Internals: how SeBS builds and deploys functions?](docs/build.md)
* [Internals: how SeBS package is designed?](docs/design.md)
* [Modularity: how to extend SeBS with new benchmarks, experiments, and platforms?](docs/modularity.md)

Do you have further questions that were not answered by our documentation?
Did you encounter trouble installing and using SeBS?
Or do you want to use SeBS in your work and you need new features?
[Join our community on Slack](https://join.slack.com/t/serverlessbenchmark/shared_invite/zt-30622ov74-_S9QeDjAJLZSe9bJC8tStw) or open a GitHub issue.


## Installation

Requirements:
- Docker (at least 19)
- Python 3.10+ with `pip` + `venv` or `uv`
- `libcurl` and its headers must be available on your system to install `pycurl`
- Standard Linux tools and `zip` installed

... and that should be all. We currently support Linux and other POSIX systems with Bash available. On Windows, we recommend using WSL.

> [!WARNING]
> Please do not use SeBS with `sudo`. There is no requirement to use any superuser permissions. **Make sure** that your Docker daemon is running and your user has sufficient permissions to use it (see [Docker documentation](https://docs.docker.com/engine/install/linux-postinstall/) on configuring your user to have non-sudo access to containers). Otherwise, you might see many "Connection refused" and "Permission denied" errors when using SeBS.

SeBS can be installed in one of three ways:

### 1. Package Install (Recommended for Users)

Install SeBS directly from PyPI with your favorite tools:

```bash
pip install serverless-benchmarks
sebs --help

uv pip install serverless-benchmarks
uv run sebs --help
```

Now you can deploy serverless experiments :-) Benchmarks data will be automatically cloned to `~/.sebs/benchmarks-data/` on first benchmark use.

To verify the correctness of installation, you can use [our regression testing](docs/usage.md#regression).

### 2. Git Install (For Contributors)

For developers who want to modify SeBS or contribute to the project:

```bash
git clone https://github.com/spcl/serverless-benchmarks.git
cd serverless-benchmarks
# -e for editable install, i.e, changes are immediately visible in the package
# [dev] adds developer dependencies, e.g., for code linting
pip install -e '.[dev]'
sebs --help

# alternative
uv sync --extra dev
uv run sebs --help
```

### 3. Legacy Development Install

This method is deprecated and will be removed in future releases. It is recommended to use the Git Install method instead.

```bash
git clone https://github.com/spcl/serverless-benchmarks.git
cd serverless-benchmarks
./install.py --aws --azure --gcp --openwhisk --local
```

This will create a virtual environment in `python-venv`, and install necessary Python
dependencies and third-party dependencies. To use SeBS, you must first activate the new Python virtual environment:

```bash
. python-venv/bin/activate
python -m sebs.cli --help
```

The installation of additional platforms is controlled with the `--{platform}` and `--no-{platform}` switches. Currently, the default behavior for `install.py` is to install only the local environment.

## Lembrete: comandos para testar OpenFaaS no WSL

### Clonar

```bash
git clone https://github.com/josedhontas/serverless-benchmarks.git
cd serverless-benchmarks
```

### Benchmarks-data

```bash
git clone https://github.com/spcl/serverless-benchmarks-data.git benchmarks-data
rm -rf benchmarks-data/.git
```

### Config

```json
"gateway": "http://127.0.0.1:8080",
"faasCli": "faas-cli"
```

```json
"dockerhubRepository": "your-dockerhub-user/serverless-benchmarks"
```

```bash
docker login
```

### Gateway

```bash
kubectl port-forward -n openfaas svc/gateway 8080:8080
```

```bash
curl http://127.0.0.1:8080/system/functions
```

```bash
PASSWORD=$(kubectl -n openfaas get secret basic-auth -o jsonpath="{.data.basic-auth-password}" | base64 --decode)
faas-cli login --gateway http://127.0.0.1:8080 --username admin --password "$PASSWORD"
```

### Rodar com rebuild

```bash
python3 -m sebs.cli benchmark invoke 110.dynamic-html test \
  --config configs/openfaas.json \
  --deployment openfaas \
  --update-code \
  --verbose
```

### Rodar sem rebuild

```bash
python3 -m sebs.cli benchmark invoke 110.dynamic-html test \
  --config configs/openfaas.json \
  --deployment openfaas \
  --verbose
```

### Resultado

```bash
cat experiments.json
```

### Teste manual

```bash
FN=sebs-6dbc6478-110-dynamic-html-python-3-11
```

```bash
curl -v http://127.0.0.1:8080/function/$FN/_/health
```

```bash
curl -s -v \
  -H "Content-Type: application/json" \
  -d '{"username":"teste","random_len":10}' \
  http://127.0.0.1:8080/function/$FN
```

### Remover funcao

```bash
faas-cli remove \
  --name sebs-6dbc6478-110-dynamic-html-python-3-11 \
  --gateway http://127.0.0.1:8080 \
  --namespace openfaas-fn
```

### Recriar funcao

```bash
python3 -m sebs.cli benchmark invoke 110.dynamic-html test \
  --config configs/openfaas.json \
  --deployment openfaas \
  --update-code \
  --verbose
```

### Debug

```bash
FN=sebs-6dbc6478-110-dynamic-html-python-3-11

kubectl get pods -n openfaas-fn -o wide
kubectl get deploy -n openfaas-fn
kubectl describe pod -n openfaas-fn -l faas_function=$FN
kubectl logs -n openfaas-fn deploy/$FN --tail=100
```

## Lembrete: comandos para testar Fission no WSL

### Pre-requisitos

O Fission precisa estar instalado no cluster Kubernetes, e o CLI `fission`,
`kubectl` e `docker` precisam funcionar no WSL:

```bash
docker ps
kubectl get nodes
fission version
fission check
```

### Benchmarks-data

Se o clone nao tiver o diretorio `benchmarks-data`, baixe os dados:

```bash
git clone https://github.com/spcl/serverless-benchmarks-data.git benchmarks-data
rm -rf benchmarks-data/.git
```

### Config

No arquivo `configs/fission.json`, ajuste o repositorio Docker para uma imagem
que o cluster consiga puxar:

```json
"dockerhubRepository": "your-dockerhub-user/serverless-benchmarks"
```

Depois faca login no Docker Hub:

```bash
docker login
```

Para o teste simples com `110.dynamic-html`, nao configure storage no
`configs/fission.json`. Esse benchmark nao precisa de MinIO/ScyllaDB.

### Router

Exponha o router do Fission em outro terminal e deixe esse comando rodando:

```bash
kubectl port-forward -n fission svc/router 8888:80
```

Teste se o router responde:

```bash
curl -i http://127.0.0.1:8888/
```

### Rodar com rebuild

```bash
python3 -m sebs.cli benchmark invoke 110.dynamic-html test \
  --config configs/fission.json \
  --deployment fission \
  --architecture x64 \
  --system-variant container \
  --repetitions 1 \
  --update-code \
  --timeout 120 \
  --verbose \
  --output-dir out-fission-fixed
```

### Rodar sem rebuild

```bash
python3 -m sebs.cli benchmark invoke 110.dynamic-html test \
  --config configs/fission.json \
  --deployment fission \
  --architecture x64 \
  --system-variant container \
  --repetitions 1 \
  --timeout 120 \
  --verbose \
  --output-dir out-fission-fixed-2
```

### Resultado

O SeBS salva o resultado em `experiments.json` dentro do diretorio passado em
`--output-dir`:

```bash
python3 -m json.tool out-fission-fixed/experiments.json | less
```

Com `jq`:

```bash
jq '.invocations' out-fission-fixed/experiments.json
jq -r '.invocations[0].output.result.result' out-fission-fixed/experiments.json | head -40
```

### Teste com storage object no Fission

Para benchmarks que usam object storage, suba o MinIO pelo SeBS e salve a
configuracao gerada:

```bash
python3 -m sebs.cli storage start object configs/storage.json \
  --output-json storage-object.json
```

No WSL, descubra o IP que o processo local do SeBS consegue usar:

```bash
hostname -I | awk '{print $1}'
```

Atualize o endereco do MinIO no arquivo gerado. Troque `172.31.213.9` pelo IP
retornado no comando anterior:

```bash
jq '.object.minio.address = "172.31.213.9:9011"' storage-object.json > /tmp/storage-object.json
mv /tmp/storage-object.json storage-object.json
```

Antes de rodar o benchmark, confirme se um pod do Kubernetes consegue chegar no
MinIO:

```bash
kubectl run curltest --rm -i --restart=Never \
  --image=curlimages/curl -- \
  -sS -o /dev/null -w "%{http_code}\n" \
  http://host.docker.internal:9011/minio/health/live
```

O esperado e `200`. Para validar Fission + MinIO, use `311.compression`, porque
ele usa dados locais do `benchmarks-data` e nao depende de URL externa:

```bash
python3 -m sebs.cli benchmark invoke 311.compression test \
  --config configs/fission.json \
  --deployment fission \
  --architecture x64 \
  --system-variant container \
  --storage-configuration storage-object.json \
  --repetitions 1 \
  --update-code \
  --update-storage \
  --timeout 180 \
  --verbose \
  --validate \
  --output-dir out-fission-compression
```

O teste passou quando aparecer:

```text
Invoke of function was successful
output validation passed
Save results to .../out-fission-compression/experiments.json
```

Para ver o resultado bruto com `cat`:

```bash
cat out-fission-compression/experiments.json
```

Se quiser ver so o comeco do arquivo:

```bash
cat out-fission-compression/experiments.json | head -n 80
```

O benchmark `120.uploader` tambem usa storage, mas depende de uma URL externa da
Wikimedia. Se ele falhar com `HTTP Error 400: Use thumbnail sizes...`, isso e
problema da URL usada pelo benchmark, nao necessariamente do Fission ou do
MinIO.

### Teste manual da funcao HTML

Se quiser testar a imagem gerada sem passar pelo SeBS, crie uma funcao curta:

```bash
fission route delete --name sebsraw || true
fission fn delete --name sebsraw || true

fission fn run-container \
  --name sebsraw \
  --image your-dockerhub-user/serverless-benchmarks:function.fission.110.dynamic-html.python-3.11-x64-1.2.1 \
  --port 8080

fission route create \
  --name sebsraw \
  --function sebsraw \
  --url /sebsraw \
  --method POST

kubectl wait --for=condition=ready pod \
  -l functionName=sebsraw \
  -n default \
  --timeout=180s
```

Invoque a funcao:

```bash
curl -i -X POST http://127.0.0.1:8888/sebsraw \
  -H 'Content-Type: application/json' \
  -d '{"username":"testname","random_len":10}'
```

### Debug

```bash
FN=sebsraw

fission fn list
fission route list
fission fn pods --name $FN

kubectl get pods -A --show-labels | grep $FN || true
kubectl get deploy -A | grep $FN || true
kubectl get svc -A | grep $FN || true

kubectl -n fission logs deploy/executor --tail=120
kubectl -n fission logs deploy/router --tail=80
```

Se o pod ficar em `ImagePullBackOff`, o cluster nao conseguiu baixar a imagem.
Verifique se o repositorio Docker existe, se esta publico ou se o cluster tem
`imagePullSecret` configurado.
