# Atualizações do Track Metadata Scanner

Versão atual: 1.1.0.

O botão Buscar atualizações consulta a última release pública estável do
repositório TruePabloEscobar/Analisador-de-Metadata-Musical. Commits isolados
não são instaláveis: publique uma release com tag vMAJOR.MINOR.PATCH e anexe
o executável Windows com nome Track.Metadata.Scanner.exe.

O GitHub deve fornecer digest SHA-256 para o asset. O aplicativo verifica
versão, origem, tamanho, assinatura MZ e checksum antes de instalar.
O usuário confirma a instalação e o reinício. A pasta do EXE deve permitir
escrita. A substituição espera o processo encerrar e mantém o EXE anterior
com sufixo .previous. Falhas ficam em scanner-update-*/update.log.

Para publicar: atualize VERSION em updater.py, execute os testes, compile
com build.ps1 e anexe o resultado à release. Não é necessário instalar Git
no computador do usuário. Uma resposta 404 pode significar ausência de
release pública ou repositório privado; o aplicativo registra esse motivo.
