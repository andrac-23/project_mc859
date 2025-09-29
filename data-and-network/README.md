# Coleta de Dados e Rede

A criação da rede é ligada com a coleta de dados num processo de pipeline. Inicialmente, os lugares são gerados e as atrações obtidas. Para cada atração, suas análises do Google Maps são coletadas e seus adjetivos e emoções são extraidos. Finalmente, os nós e arestas do grafo são criados.

O processo de pipeline permite que a coleta de dados seja facilmente interrompida e resumida em um tempo posterior. O comando `just clear_data_to_network_pipeline` pode ser executado para apagar todo o progresso atual e recomeçar o processo de coleta de dados.

O arquivo `attraction-sentiment-net-info.json` contém as informacoes da rede construída para o projeto e o grafo final está no arquivo `attraction-sentiment-net.gml`.

O comando `just run_data_to_network_pipeline` inicia/resume o processo de extração de dados e construção da rede.
