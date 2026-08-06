package demo.chatclient.rag;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.document.Document;
import org.springframework.ai.vectorstore.SearchRequest;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.stream.Collectors;

@Service
public class DemoChatService implements DemoChatClient {

    private static final String SYSTEM = """
            You answer the user's question using ONLY the context provided.
            The context is content fetched from web pages. If the context contains
            nothing relevant, say so plainly instead of guessing. Be concise.""";

    private final ChatClient chatClient;
    private final VectorStore vectorStore;
    private final int topK;

    public DemoChatService(ChatClient.Builder chatClientBuilder,
                           VectorStore vectorStore,
                           @Value("${app.rag.top-k:5}") int topK) {
        this.chatClient = chatClientBuilder.defaultSystem(SYSTEM).build();
        this.vectorStore = vectorStore;
        this.topK = topK;
    }

    @SuppressWarnings("null")
    @Override
    public Answer askQuestion(Question question) {
        List<Document> hits = retrieve(question.question(), topK);
        String context = hits.stream()
                .map(Document::getText)
                .collect(Collectors.joining("\n\n"));

        String response = chatClient.prompt()
            .user(u -> u.text("""
                    Context:

                    {context}

                    Question: {question}""")
                    .param("context", context)
                    .param("question", question.question()))
            .call()
            .content();
        return new Answer(response);
    }

    private List<Document> retrieve(String question, int k) {
        return vectorStore.similaritySearch(
                SearchRequest.builder().query(question).topK(k).build());
    }
}