# Ferramentas locais

Instale o pacote conforme o README da raiz e execute:

- Simulação de movimentos: `python -m vessel_monitor.simulation.simular_praticagem`.
- Exibir teste no observador: `python -m vessel_monitor.simulation.simular_praticagem --observador`.
- Teste TOXOTIS: acrescente `--toxotis` ao comando anterior.
- Comparar capturas: `python -m vessel_monitor.simulation.comparar_capturas_praticagem --help`.
- Chat local: `python -m vessel_monitor --simular-chat TELEFONE`.

As funções de simulação ficam no pacote para que o observador também possa
utilizá-las. As simulações de movimentação são isoladas dos dados reais.
