1. Launch a new virtual machine and shell into it:

```
multipass launch --cpus 4 --disk 80G --memory 24G --name rag-demo 24.04
multipass shell rag-demo
```

2. Install concierge and provision for the k8s preset 
```
sudo snap install concierge --classic
sudo concierge prepare -p k8s --charmcraft-channel latest/edge
```

3. Update the load balancer to serve under the machine’s main IP and install an OCI image registry:
```
PREFSRC=$(ip -4 -j route get 2.2.2.2 | jq -r '.[] | .prefsrc')
sudo k8s set load-balancer.cidrs=$PREFSRC/32
curl https://raw.githubusercontent.com/canonical/spring-petclinic/refs/heads/resources/registry.yaml | kubectl apply -f - 
```

4. Create an lxd controller and add new models

Step (2) created a controller named `concierge-k8s` which is a k8s controller. This cannot be used
to deploy charms for snaps. Create an lxd controller.
```
juju bootstrap localhost lxd
```

Add a model named `ai` under the `lxd` controller. The various snap charms are deployed under this.
```
juju add-model lxd
```

Add a model named `rag-demo` under the `concierge-k8s` controller. The Spring AI app charm is deployed under this.
```
juju switch concierge-k8s
juju add-model rag-demo
```
<img width="1136" height="188" alt="image" src="https://github.com/user-attachments/assets/7a34e6ab-49d4-48f0-9ed9-3bf1a9aa3872" />

5. Deploy opensearch charm
```
sudo sysctl -w vm.max_map_count=262144 vm.swappiness=0 net.ipv4.tcp_retries2=5
juju deploy -m lxd:ai opensearch -n 2 --channel 2/stable
juju deploy -m lxd:ai self-signed-certificates --channel 1/stable
juju integrate -m lxd:ai opensearch:certificates self-signed-certificates
```
<img width="1300" height="447" alt="Screenshot From 2026-10-16 12-06-21" src="https://github.com/user-attachments/assets/7a0e1c79-0806-440c-a21a-772d9b266c91" />

6. Deploy postgresql charm
```
juju deploy -m lxd:ai postgresql --channel 16/stable --config plugin_vector_enable=true
```
<img width="1341" height="525" alt="Screenshot From 2026-10-16 12-31-57" src="https://github.com/user-attachments/assets/c46dc6d0-b5e3-4315-96a6-96bdf6e033f4" />

7. Deploy the ollama charm
```
git clone https://github.com/pushkarnk/ollama-charm.git
cd ollama-charm
charmcraft pack
juju deploy -m lxd:ai ./ollama-snap_amd64.charm ollama
```
<img width="1529" height="605" alt="Screenshot From 2026-10-16 13-39-31" src="https://github.com/user-attachments/assets/656c31c7-f5e8-428a-a950-b2d052f65565" />

9. Deploy the inference-snap-operator charm
```
git clone https://github.com/ktsakalozos-canonical/inference-snap-operator.git
cd inference-snap-operator
charmcraft pack
juju deploy -m lxd:ai ./inference-snap_ubuntu-24.04-amd64.charm inference
```
Installs gemma3 by default.

<img width="1538" height="682" alt="Screenshot From 2026-10-16 15-11-18" src="https://github.com/user-attachments/assets/b92b42a2-81ff-4d59-8c26-c4564118dc36" />

10. Now, offer endpoints from apps deployed under lxd:ai for other apps to consume
```
juju offer -c lxd ai.ollama:ollama ollama
juju offer -c lxd ai.opensearch:opensearch-client opensearch
juju offer -c lxd ai.inference:inference-api inference
juju offer -c lxd ai.postgresql:database postgresql
```

11. Build a Rock and Charm for the Spring AI RAG demo application
```
git clone https://github.com/pushkarnk/spring-ai-rag-demo.git && cd spring-ai-rag-demo
ROCKCRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS=True rockcraft pack
rockcraft.skopeo copy --insecure-policy --dest-tls-verify=false oci-archive:spring-ai-rag-demo_0.1_amd64.rock docker://localhost:32000/spring-ai-rag-demo:0.1
cd charm && charmcraft pack
```

12. Deploy the Spring AI RAG demo application
```
juju deploy -m concierge-k8s:rag ./rag-app_amd64.charm rag-app --resource app-image=localhost:32000/spring-ai-rag-demo:0.1 --config app-profiles=tls
```
<img width="1346" height="273" alt="Screenshot From 2026-10-16 21-45-19" src="https://github.com/user-attachments/assets/db12fc27-e7c9-49d4-b6d2-98a9fd688df7" />

13. Integrate with ollama, opensearch and inference-snap charms
```
juju consume -m concierge-k8s:rag-demo lxd:admin/ai.inference
juju consume -m concierge-k8s:rag-demo lxd:admin/ai.ollama
juju consume -m concierge-k8s:rag-demo lxd:admin/ai.opensearch
```
```
juju integrate -m concierge-k8s:rag-demo rag-app:embedding ollama
juju integrate -m concierge-k8s:rag-demo rag-app:inference inference
juju integrate -m concierge-k8s:rag-demo rag-app:opensearch opensearch
```
<img width="1307" height="420" alt="Screenshot From 2026-10-16 22-51-57" src="https://github.com/user-attachments/assets/9d0a6939-90b6-47fc-bfbf-69221db68a50" />


14. Deploy traefik and integrate Spring AI RAG application with it. Then access it in a browser.
```
juju switch concierge-k8s
juju deploy traefik-k8s --trust
juju integrate rag-app traefik-k8s
```
15. Run a RAG query: ingestion + 
15. Try changing the model to qwen3

16. Try changing the vectordb from opensearch to postgresql
