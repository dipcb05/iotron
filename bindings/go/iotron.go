package iotron

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

type Client struct {
	BaseURL string
	APIKey  string
	Client  *http.Client
}

type FlashRequest struct {
	Board    string `json:"board"`
	Artifact string `json:"artifact"`
	Port     string `json:"port,omitempty"`
	FQBN     string `json:"fqbn,omitempty"`
	Execute  bool   `json:"execute"`
}

type OTARequest struct {
	Board       string `json:"board"`
	Artifact    string `json:"artifact"`
	Host        string `json:"host"`
	Username    string `json:"username,omitempty"`
	Destination string `json:"destination,omitempty"`
	Execute     bool   `json:"execute"`
}

type DeviceRequest struct {
	DeviceID string         `json:"device_id"`
	Board    string         `json:"board"`
	Protocol string         `json:"protocol,omitempty"`
	Network  string         `json:"network,omitempty"`
	Metadata map[string]any `json:"metadata,omitempty"`
}

type DeviceHeartbeatRequest struct {
	DeviceID string `json:"device_id"`
}

type TelemetryRequest struct {
	DeviceID   string `json:"device_id"`
	Metric     string `json:"metric"`
	Value      any    `json:"value"`
	RecordedAt string `json:"recorded_at,omitempty"`
}

func NewClient(baseURL, apiKey string) *Client {
	return &Client{
		BaseURL: strings.TrimRight(baseURL, "/"),
		APIKey:  apiKey,
		Client:  &http.Client{Timeout: 15 * time.Second},
	}
}

func (c *Client) Health() (map[string]any, error) {
	return c.getJSON("/health")
}

func (c *Client) State() (map[string]any, error) {
	return c.getJSON("/project/state")
}

func (c *Client) BackendOverview() (map[string]any, error) {
	return c.getJSON("/backend/overview")
}

func (c *Client) NativeManifest() (map[string]any, error) {
	return c.getJSON("/native/manifest")
}

func (c *Client) Toolchains() ([]map[string]any, error) {
	payload, err := c.getJSONArray("/catalog/toolchains")
	if err != nil {
		return nil, err
	}
	return payload, nil
}

func (c *Client) Devices() ([]map[string]any, error) {
	return c.getJSONArray("/devices")
}

func (c *Client) Telemetry(deviceID string, limit int) ([]map[string]any, error) {
	path := "/telemetry"
	params := []string{}
	if deviceID != "" {
		params = append(params, "device_id="+url.QueryEscape(deviceID))
	}
	if limit > 0 {
		params = append(params, fmt.Sprintf("limit=%d", limit))
	}
	if len(params) > 0 {
		path += "?" + strings.Join(params, "&")
	}
	return c.getJSONArray(path)
}

func (c *Client) Flash(request FlashRequest) (map[string]any, error) {
	return c.postJSON("/project/flash", request)
}

func (c *Client) OTA(request OTARequest) (map[string]any, error) {
	return c.postJSON("/project/ota", request)
}

func (c *Client) RegisterDevice(request DeviceRequest) (map[string]any, error) {
	return c.postJSON("/devices/register", request)
}

func (c *Client) HeartbeatDevice(deviceID string) (map[string]any, error) {
	return c.postJSON("/devices/heartbeat", DeviceHeartbeatRequest{DeviceID: deviceID})
}

func (c *Client) IngestTelemetry(request TelemetryRequest) (map[string]any, error) {
	return c.postJSON("/telemetry", request)
}

func (c *Client) getJSON(path string) (map[string]any, error) {
	request, err := http.NewRequest(http.MethodGet, c.BaseURL+path, nil)
	if err != nil {
		return nil, err
	}
	payload, err := c.do(request)
	if err != nil {
		return nil, err
	}
	object, ok := payload.(map[string]any)
	if !ok {
		return nil, fmt.Errorf("expected object response from %s", path)
	}
	return object, nil
}

func (c *Client) getJSONArray(path string) ([]map[string]any, error) {
	request, err := http.NewRequest(http.MethodGet, c.BaseURL+path, nil)
	if err != nil {
		return nil, err
	}
	payload, err := c.do(request)
	if err != nil {
		return nil, err
	}
	list, ok := payload.([]map[string]any)
	if !ok {
		return nil, fmt.Errorf("expected array response from %s", path)
	}
	return list, nil
}

func (c *Client) postJSON(path string, body any) (map[string]any, error) {
	encoded, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}
	request, err := http.NewRequest(http.MethodPost, c.BaseURL+path, bytes.NewReader(encoded))
	if err != nil {
		return nil, err
	}
	request.Header.Set("Content-Type", "application/json")
	payload, err := c.do(request)
	if err != nil {
		return nil, err
	}
	object, ok := payload.(map[string]any)
	if !ok {
		return nil, fmt.Errorf("expected object response from %s", path)
	}
	return object, nil
}

func (c *Client) do(request *http.Request) (any, error) {
	if c.APIKey != "" {
		request.Header.Set("X-API-Key", c.APIKey)
	}
	response, err := c.Client.Do(request)
	if err != nil {
		return nil, err
	}
	defer response.Body.Close()

	payload, err := io.ReadAll(response.Body)
	if err != nil {
		return nil, err
	}
	if response.StatusCode >= 400 {
		return nil, fmt.Errorf("iotron api error: %s", string(payload))
	}

	var object map[string]any
	if err := json.Unmarshal(payload, &object); err == nil {
		return object, nil
	}

	var list []map[string]any
	if err := json.Unmarshal(payload, &list); err == nil {
		return list, nil
	}

	return nil, fmt.Errorf("unexpected response payload: %s", string(payload))
}
