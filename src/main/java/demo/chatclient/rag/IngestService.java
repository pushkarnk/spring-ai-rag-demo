package demo.chatclient.rag;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.document.Document;
import org.springframework.ai.transformer.splitter.TokenTextSplitter;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.net.URI;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Service
public class IngestService {

    private static final Logger log = LoggerFactory.getLogger(IngestService.class);

    private final VectorStore vectorStore;
    private final int batchSize;
    private final TokenTextSplitter textSplitter;
    private final RestClient httpClient;

    public IngestService(VectorStore vectorStore,
                         @Value("${app.rag.ingest.batch-size:16}") int batchSize,
                         @Value("${app.rag.ingest.chunk-size:300}") int chunkSize) {
        this.vectorStore = vectorStore;
        this.batchSize = batchSize;
        this.textSplitter = TokenTextSplitter.builder().withChunkSize(chunkSize).build();
        this.httpClient = RestClient.builder()
                .defaultHeader("User-Agent", "chat-client/rag")
                .build();
    }

    // fetch text from the urls, embed and index it
    public IngestResult ingest(List<String> urls) {
        List<Document> documents = new ArrayList<>();
        int skipped = 0;
        for (String url : urls) {
            try {
                String content = fetch(url);
                if (content.isBlank()) {
                    skipped++;
                    continue;
                }
                documents.addAll(this.textSplitter.split(toDocument(url, content)));
            } catch (Exception e) {
                log.warn("Skipping {}: {}", url, e.getMessage());
                skipped++;
            }
        }

        log.info("Embedding and indexing {} documents (skipped {})...", documents.size(), skipped);
        for (int from = 0; from < documents.size(); from += batchSize) {
            int to = Math.min(from + batchSize, documents.size());
            vectorStore.add(documents.subList(from, to));
            log.info("  indexed {}/{}", to, documents.size());
        }

        return new IngestResult(urls.size(), documents.size(), skipped);
    }

    // get text from the url
    private String fetch(String url) {
        return httpClient.get()
                .uri(URI.create(url))
                .retrieve()
                .body(String.class);
    }

    // strip HTML tags, keep the raw URL as metadata
    private static Document toDocument(String url, String body) {
        String text = looksLikeHtml(body) ? stripHtml(body) : body;
        Map<String, Object> metadata = Map.of("url", url);
        return new Document(text, metadata);
    }

    private static boolean looksLikeHtml(String body) {
        String lower = body.length() > 512 ? body.substring(0, 512) : body;
        return lower.toLowerCase().contains("<html") || lower.toLowerCase().contains("<body");
    }

    // drop tags and whitespaces
    private static String stripHtml(String html) {
        return html.replaceAll("(?s)<script.*?</script>", " ")
                .replaceAll("(?s)<style.*?</style>", " ")
                .replaceAll("(?s)<[^>]+>", " ")
                .replaceAll("&nbsp;", " ")
                .replaceAll("\\s+", " ")
                .trim();
    }

    public record IngestResult(int submitted, int indexed, int skipped) {}
}