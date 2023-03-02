import {
  Button,
  Divider,
  Typography,
  Modal,
  Input,
  Table,
  Menu,
  Dropdown,
  Checkbox,
 DatePicker } from "antd";
import dayjs from "dayjs";
import React, { useState } from "react";
import { useQuery, useMutation, QueryClient } from "react-query";
import { MoreOutlined } from "@ant-design/icons";
import { toast } from "react-toastify";
import { Webhook, APIKey } from "../../../../api/api";
import {
  WebhookEndpoint,
  WebhookEndpointCreate,
} from "../../../../types/webhook-type";
import CopyText from "../../../base/CopytoClipboard";
import {
  APIKeyType,
  APIKeyCreate,
  APIKeyCreateResponse,
} from "../../../../types/apikey-type";

function isValidHttpUrl(string) {
  let url;
  try {
    url = new URL(string);
  } catch (_) {
    return false;
  }
  return url.protocol === "https:";
}
export function DeveloperTab() {
  const [visible, setVisible] = useState<boolean>(false);
  const [visibleWebhook, setVisibleWebhook] = useState<boolean>(false);
  const [visibleAPIKey, setVisibleAPIKey] = useState<boolean>(false);
  const [apiKey, setApiKey] = useState<string>("");
  const queryClient = new QueryClient();
  const [webhookName, setWebhookName] = useState<string>("");
  const [webhookUrl, setWebhookUrl] = useState<string>("");
  const [apiKeyName, setAPIKeyName] = useState<string>("");
  const [apiKeyExpire, setAPIKeyExpire] = useState<string>("");
  const [webhookSelected, setWebhookSelected] = useState<WebhookEndpoint>();
  const [apiKeySelected, setApiKeySelected] = useState<APIKeyType>();
  const [isCustomerCreated, setIsCustomerCreated] = useState<boolean>(false);
  const [isInvoiceGenerated, setIsInvoiceGenerated] = useState<boolean>(false);
  const [isInvoicePaid, setIsInvoicePaid] = useState<boolean>(false);
  const [isUsageAlertTriggered, setIsUsageAlertTriggered] =
    useState<boolean>(false);
  const closeModal = () => {
    setVisible(false);
    setApiKey("");
  };

  const closeWebhookModal = () => {
    setVisibleWebhook(false);
  };

  const closeAPIKeyModal = () => {
    setVisibleAPIKey(false);
  };

  const webhookMenu = (
    <Menu>
      <Menu.Item
        key="2"
        onClick={() => handleDeleteUrl(webhookSelected?.webhook_endpoint_id)}
      >
        <div className="planMenuArchiveIcon">
          <div className="archiveLabel">Delete</div>
        </div>
      </Menu.Item>
    </Menu>
  );
  const apiKeyMenu = (
    <Menu>
      <div>
        <Menu.Item
          key="2"
          onClick={() => handleDeleteKey(apiKeySelected?.prefix)}
        >
          <div className="planMenuArchiveIcon">
            <div className="archiveLabel">Delete Key</div>
          </div>
        </Menu.Item>
      </div>
      <Menu.Item key="2" onClick={() => handleRollKey(apiKeySelected?.prefix)}>
        <div className="planMenuArchiveIcon">
          <div className="archiveLabel">Roll Key</div>
        </div>
      </Menu.Item>
    </Menu>
  );

  const {
    isLoading: isLoadingWebhook,
    data: webhookData,
    refetch: refetchWebhook,
  } = useQuery("webhook_urls", () => Webhook.getEndpoints());

  const { data: apiKeyData, refetch: refetchAPIKey } = useQuery(
    "api_keys",
    () => APIKey.getKeys()
  );

  const createWebhookMutation = useMutation(
    (endpointPost: WebhookEndpointCreate) =>
      Webhook.createEndpoint(endpointPost),
    {
      onSuccess: () => {
        queryClient.invalidateQueries("webhook_urls");
        refetchWebhook();
        setWebhookUrl("");
        setWebhookName("");
        setIsCustomerCreated(false);
        setIsInvoiceGenerated(false);
        setIsInvoicePaid(false);
        setIsUsageAlertTriggered(false);
        toast.success("Webhook URL added successfully");
        setVisibleWebhook(false);
        setWebhookSelected(undefined);
      },
      onError: (error) => {
        toast.error(error.response.title);
      },
    }
  );

  const createAPIKeyMutation = useMutation(
    (apiKey: APIKeyCreate) => APIKey.createKey(apiKey),
    {
      onSuccess: (record: APIKeyCreateResponse) => {
        queryClient.invalidateQueries("api_keys");
        refetchAPIKey();
        setAPIKeyName("");
        toast.success("API Key added successfully");
        setVisibleAPIKey(false);
        setApiKeySelected(undefined);
        setApiKey(record.key);
        setVisible(true);
      },
      onError: (error) => {
        toast.error(error.response.title);
      },
    }
  );

  const handleAddUrl = () => {
    if (!isValidHttpUrl(`https://${webhookUrl}`)) {
      toast.error("Please enter a valid URL");
      return;
    }

    if (!webhookName) {
      toast.error("Please enter webhook name");
      return;
    }

    if (!isCustomerCreated && !isInvoiceGenerated && !isInvoicePaid && !isUsageAlertTriggered) {
      toast.error("Please select at-least one trigger");
      return;
    }

    const triggers: string[] = [];
    if (isCustomerCreated) {
      triggers.push("customer.created");
    }
    if (isInvoiceGenerated) {
      triggers.push("invoice.created");
    }
    if (isInvoicePaid) {
      triggers.push("invoice.paid");
    }
    if (isUsageAlertTriggered) {
      triggers.push("usage_alert.triggered");
    }
    const endpointPost: WebhookEndpointCreate = {
      name: webhookName,
      webhook_url: new URL(`https://${webhookUrl}`),
      triggers_in: triggers,
    };
    createWebhookMutation.mutate(endpointPost);
  };

  const handleAddAPIKey = () => {
    if (!apiKeyName) {
      toast.error("Please enter API Key name");
      return;
    }

    const endpointPost: APIKeyCreate = {
      name: apiKeyName,
    };
    // if expiry date is a datetime parseable string, include it in endpointPost
    if (apiKeyExpire !== undefined && apiKeyExpire !== "") {
      endpointPost.expiry_date = apiKeyExpire;
    }

    createAPIKeyMutation.mutate(endpointPost);
  };

  const handleDeleteUrl = (id: string | undefined) => {
    if (id) {
      Webhook.deleteEndpoint(id)
        .then((data) => {
          toast.success("Webhook URL deleted successfully");
          queryClient.invalidateQueries("webhook_urls");
          setWebhookSelected(undefined);
          refetchWebhook();
        })
        .catch((err) => {
          toast.error("Error deleting webhook URL");
        });
    }
  };

  const handleDeleteKey = (id: string | undefined) => {
    if (id) {
      APIKey.deleteKey(id)
        .then((data) => {
          toast.success("API Key deleted successfully");
          queryClient.invalidateQueries("api_keys");
          setApiKeySelected(undefined);
          refetchAPIKey();
        })
        .catch((err) => {
          toast.error("Error deleting API Key");
        });
    }
  };

  const handleRollKey = (id: string | undefined) => {
    if (id) {
      APIKey.rollKey(id)
        .then((data) => {
          toast.success("API Key rolled successfully");
          queryClient.invalidateQueries("api_keys");
          setApiKeySelected(undefined);
          refetchAPIKey();
          setVisibleAPIKey(false);
          setApiKey(data.key);
          setVisible(true);
        })
        .catch((err) => {
          toast.error("Error rolling API Key");
        });
    }
  };

  if (isLoadingWebhook) return <div>Loading...</div>;
  return (
    <div>
      <div className="mt-10 flex flex-row justify-between w-full mb-8">
        <Typography.Title level={2}>API Keys</Typography.Title>
        <Button
          type="primary"
          onClick={() => {
            setAPIKeyName("");
            setAPIKeyExpire("");
            setVisibleAPIKey(true);
          }}
        >
          Add API Key
        </Button>
      </div>
      <div className="border-2 border-solid rounded border-[#EAEAEB]">
        <Table
          dataSource={apiKeyData}
          pagination={false}
          columns={[
            {
              title: "Name",
              dataIndex: "name",
              key: "name",
            },
            {
              title: "Key",
              dataIndex: "prefix",
              key: "prefix",
              render: (prefix: string) => <div className="font-menlo">{prefix}•••</div>,
            },
            {
              title: "Expiry Date",
              dataIndex: "expiry_date",
              key: "expiry_date",
            },
            {
              title: "Created At",
              dataIndex: "created",
              key: "created",
              render: (created: string) => <div>{dayjs(created).format("DD MMM YYYY, hh:mm")}</div>,
            },
            {
              key: "action",
              width: 100,
              render: (text: any, record: any) => (
                <Dropdown overlay={apiKeyMenu} trigger={["click"]}>
                  <Button
                    type="text"
                    size="small"
                    onClick={(e) => {
                      setApiKeySelected(record);
                      e.preventDefault();
                    }}
                  >
                    <MoreOutlined />
                  </Button>
                </Dropdown>
              ),
            },
          ]}
        />
      </div>
      <Divider />
      <div className="mt-10 flex flex-row justify-between w-full mb-8">
        <Typography.Title level={2}>Webhooks</Typography.Title>
        <Button
          type="primary"
          onClick={() => {
            setWebhookUrl("");
            setWebhookName("");
            setVisibleWebhook(true);
          }}
        >
          Add URL
        </Button>
      </div>

      <div className="border-2 border-solid rounded border-[#EAEAEB]">
        <Table
          dataSource={webhookData}
          pagination={false}
          columns={[
            {
              title: "Name",
              dataIndex: "name",
              key: "name",
            },
            {
              title: "Webhook URL",
              dataIndex: "webhook_url",
              key: "webhook_url",
              render: (webhook_url: string, record) => (
                <CopyText textToCopy={webhook_url} />
              ),
            },
            {
              title: "Webhook Secret",
              dataIndex: "webhook_secret",
              key: "webhook_secret",
              render: (webhook_secret: string, record) => (
                <CopyText textToCopy={webhook_secret} />
              ),
            },
            {
              title: "Triggers",
              dataIndex: "triggers",
              key: "triggers",
              render: (triggers: object[]) => (
                  <div>
                    {triggers.map((trigger) => (
                        <div>
                          [ {trigger.trigger_name} ]
                        </div>
                      ))}
                  </div>
                ),
            },
            {
              key: "action",
              width: 100,
              render: (text: any, record: any) => (
                <Dropdown overlay={webhookMenu} trigger={["click"]}>
                  <Button
                    type="text"
                    size="small"
                    onClick={(e) => {
                      setWebhookSelected(record);
                      e.preventDefault();
                    }}
                  >
                    <MoreOutlined />
                  </Button>
                </Dropdown>
              ),
            },
          ]}
        />
      </div>

      <Modal
        visible={visibleWebhook}
        title="Webhook URL"
        onCancel={closeWebhookModal}
        footer={
          <Button
            key="Confirm URL"
            onClick={handleAddUrl}
            type="primary"
            loading={createWebhookMutation.isLoading}
          >
            Confirm
          </Button>
        }
      >
        <div className="flex flex-col space-y-8">
          <p className="text-lg font-main">Endpoint Name:</p>
          <Input
            value={webhookName}
            onChange={(e) => setWebhookName(e.target.value)}
           />
          <p className="text-lg font-main">Endpoint URL:</p>
          <Input
            addonBefore="https://"
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
           />
          <p className="text-lg font-main">Events Subscribed To:</p>
          <div className="grid grid-cols-2">
            <Checkbox
              style={{ marginLeft: "0px" }}
              onChange={(e) => setIsCustomerCreated(e.target.checked)}
              value={isCustomerCreated}
            >
              <p className="text-lg font-main">customer.created</p>
            </Checkbox>
            <Checkbox
              style={{ marginLeft: "0px" }}
              onChange={(e) => setIsInvoiceGenerated(e.target.checked)}
              value={isInvoiceGenerated}
            >
              <p className="text-lg font-main">invoice.created</p>
            </Checkbox>
            <Checkbox
              style={{ marginLeft: "0px" }}
              onChange={(e) => setIsInvoicePaid(e.target.checked)}
              value={isInvoicePaid}
            >
              <p className="text-lg font-main">invoice.paid</p>
            </Checkbox>
            <Checkbox
              style={{ marginLeft: "0px" }}
              onChange={(e) => setIsUsageAlertTriggered(e.target.checked)}
              value={isUsageAlertTriggered}
            >
              <p className="text-lg font-main">usage_alert.triggered</p>
            </Checkbox>
          </div>
        </div>
      </Modal>

      <Modal
        visible={visibleAPIKey}
        title="Create API Key"
        onCancel={closeAPIKeyModal}
        footer={
          <Button
            key="Confirm Key"
            onClick={handleAddAPIKey}
            type="primary"
            loading={createAPIKeyMutation.isLoading}
          >
            Confirm
          </Button>
        }
      >
        <div className="flex flex-col space-y-8">
          <span className="text-lg font-main">API Key Name:</span>

          <Input
            value={apiKeyName}
            className="mt-0"
            onChange={(e) => setAPIKeyName(e.target.value)}
           />
        </div>
        <div className="flex flex-col mt-10 space-y-8">
          <span className="text-lg font-main">Expiry Date + Time:</span>
          <DatePicker
            showTime
            className="mt-0"
            onChange={(date, dateString) => setAPIKeyExpire(dateString)}
          />
        </div>
      </Modal>

      <Modal
        visible={visible}
        title="New API Key"
        onCancel={closeModal}
        footer={
          <Button key="Okay" onClick={closeModal} type="primary">
            Okay
          </Button>
        }
      >
        <div className="flex flex-col">
          <p className="text-2xl font-main" />
          <p className="text-lg font-main">
            Your new key is:{" "}
            {apiKey ? <Input value={apiKey} readOnly /> : "Loading..."}
          </p>
          <p> Your API Key will only show once! Make sure to keep it safe.</p>
        </div>
      </Modal>
    </div>
  );
}
