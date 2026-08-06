package demo.chatclient.rag;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class IngestController {

    private final IngestService ingestService;

    public IngestController(IngestService ingestService) {
        this.ingestService = ingestService;
    }

    @PostMapping(path = "/ingest", produces = "application/json")
    public IngestService.IngestResult ingest(@RequestBody IngestRequest request) {
        return ingestService.ingest(request.urls());
    }
}