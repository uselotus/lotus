import {
  Button,
  Divider,
  Typography,
  Modal,
  Input,
  message,
  Popconfirm,
  Table,
  Menu,
  Dropdown,
  Checkbox,
} from "antd";
import React, { useState } from "react";
import { useQuery, useMutation, QueryClient } from "react-query";
import { Alerts, APIToken } from "../../../../api/api";
import { DeleteOutlined, MoreOutlined } from "@ant-design/icons";
import { Paper } from "../../../base/Paper";
import { toast } from "react-toastify";

export const DeveloperTab = () => {
  const [visible, setVisible] = useState<boolean>(false);
  const [visibleWebhook, setVisibleWebhook] = useState<boolean>(false);
  const [apiKey, setApiKey] = useState<string>("");
  const queryClient = new QueryClient();
  const [webhookUrl, setWebhookUrl] = useState<string>("");
  const closeModal = () => {
    setVisible(false);
    setApiKey("");
  };

  const closeWebhookModal = () => {
    setVisibleWebhook(false);
  };
  const webhookMenu = (
    <Menu>
      <Menu.Item key="1" onClick={() => setVisibleWebhook(true)}>
        <div className="planMenuArchiveIcon">
          <div>Edit</div>
        </div>
      </Menu.Item>
      <Menu.Item key="1">
        <div className="planMenuArchiveIcon">
          <div className="archiveLabel">Archive</div>
        </div>
      </Menu.Item>
    </Menu>
  );

  const {
    status: alertStatus,
    error: webhookError,
    data: webhookData,
    isLoading,
  } = useQuery<any>(["urls"], Alerts.getUrls);

  const getKey = () => {
    APIToken.newAPIToken().then((data) => {
      setApiKey(data.api_key);
    });
    setVisible(true);
  };

  const handleAddUrl = () => {
    if (webhookUrl.includes("https://")) {
      Alerts.addUrl(webhookUrl)
        .then((data) => {
          setWebhookUrl("");
          toast.success("Webhook URL added successfully");
          queryClient.invalidateQueries("urls");
          setVisibleWebhook(false);
        })
        .catch((err) => {
          toast.error("Webhook URL already exists");
        });
    } else {
      toast.error("Please enter a valid URL starting with https://");
    }
  };

  const handleDeleteUrl = (id: number) => {
    Alerts.deleteUrl(id)
      .then((data) => {
        message.success("Webhook URL deleted successfully");
      })
      .catch((err) => {
        message.error("Error deleting webhook URL");
      });
  };

  if (isLoading) return <div>Loading...</div>;
  return (
    <div>
      <div>
        <Typography.Title level={2}>API Keys</Typography.Title>
        <Typography.Paragraph>
          Requesting a new API key will revoke your existing key! Store your key
          safely.
        </Typography.Paragraph>
        <Popconfirm
          title="Are you sure to want to revoke your existing key?"
          onConfirm={getKey}
          okText="Yes"
        >
          <Button type="primary">Revoke API Key</Button>
        </Popconfirm>
      </div>
      <Divider />
      <div className="mt-10 flex flex-row justify-between w-6/12 mb-8">
        <Typography.Title level={2}>Webhooks</Typography.Title>
        <Button
          type="primary"
          onClick={() => {
            setWebhookUrl("");
            setVisibleWebhook(true);
          }}
        >
          Add URL
        </Button>
      </div>

      <div className="border-2 border-solid rounded border-[#EAEAEB] w-6/12">
        <Table
          dataSource={webhookData}
          columns={[
            {
              title: "Webhook URL",
              dataIndex: "webhook_url",
              key: "webhook_url",
            },
            {
              key: "action",
              width: 100,
              render: (text: any, record: any) => (
                <Dropdown overlay={webhookMenu} trigger={["click"]}>
                  <Button
                    type="text"
                    size="small"
                    onClick={(e) => e.preventDefault()}
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
          <Button key="Confirm URL" onClick={handleAddUrl} type="primary">
            Confirm
          </Button>
        }
      >
        <div className="flex flex-col space-y-8">
          <Input
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
          ></Input>

          <p className="text-lg font-main">Events Subscribed To:</p>
          <div className="grid grid-cols-auto">
            <Checkbox checked={true}>
              <p className="text-lg font-main">Invoice Generated</p>
            </Checkbox>
          </div>
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
          <p className="text-2xl font-main"></p>
          <p className="text-lg font-main">
            Your previous key has been revoked
          </p>
          <p className="text-lg font-main">
            Your new key is:{" "}
            {apiKey ? <Input value={apiKey} readOnly /> : "Loading..."}
          </p>
          <p></p>
        </div>
      </Modal>
    </div>
  );
};
