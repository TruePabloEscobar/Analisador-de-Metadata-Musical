# Testes

Os testes normais usam arquivos sintéticos criados em diretórios temporários. Não é necessária uma biblioteca musical pessoal e nenhum arquivo de áudio é salvo no repositório.

`validate_real.py` é opcional. Para executá-lo, defina `TRACK_SCANNER_TEST_LIBRARY` com o caminho da biblioteca no computador local. Sem essa variável, o teste informa que foi ignorado e termina com sucesso.

Os relatórios e arquivos temporários ficam fora do código versionado, conforme o `.gitignore`.
