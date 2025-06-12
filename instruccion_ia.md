## Pasos previos

### Clonar el repositorio
```
    git clone https://github.com/agcudco/modelos-llm.git
    cd modelos-llm
```
## Levantar el proyecto

### Equipos con GPU(tarjeta gráfica)

```bash
sudo docker compose --profile gpu-nvidia pull
sudo docker compose create
sudo docker compose --profile gpu-nvidia up
```

### Equipos sin GPU(tarjeta gráfica)

```bash
sudo docker compose --profile cpu pull
sudo docker compose create
sudo docker compose --profile cpu up
```