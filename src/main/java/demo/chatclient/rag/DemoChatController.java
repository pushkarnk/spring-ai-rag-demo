package demo.chatclient.rag;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import java.util.Map;

@RestController
public class DemoChatController {

    private final DemoChatClient chatClient;

    public DemoChatController(DemoChatClient chatClient) {
        this.chatClient = chatClient;
    }

    @PostMapping(path = "/ask", produces = "application/json")
    public Answer askQuestion(@RequestBody Question question) {
        return chatClient.askQuestion(question);
    }

    @GetMapping(path = "/backends", produces = "application/json")
    public Map<String, String> backends(@Value("${spring.ai.openai.chat.options.model}") String model,
                                        @Value("${spring.ai.vectorstore.type}") String vectorDb) {
        return Map.of("model", model, "vectorDb", vectorDb);
    }

}
