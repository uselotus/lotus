import React, { FC, useState } from "react";
import { useQuery, useMutation } from "react-query";
import { useNavigate } from "react-router-dom";
import { Table, Typography, Input, Button, Form, Tag } from "antd";
import { Organization } from "../../../../api/api";
import { toast } from "react-toastify";
import LoadingSpinner from "../../../../components/LoadingSpinner";

interface InviteWithEmailForm extends HTMLFormControlsCollection {
  email: string;
}

interface FormElements extends HTMLFormElement {
  readonly elements: InviteWithEmailForm;
}

const TeamTab: FC = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");

  const {
    data: organization, // organization is the data returned from the query
    isLoading,
    isError,
  } = useQuery(["organization"], () =>
    Organization.get().then((res) => {
      return res[0];
    })
  );

  const handleEmailChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setEmail(event.target.value);
  };

  const mutation = useMutation(
    (data: { email: string }) => Organization.invite(email),
    {
      onSuccess: (response) => {
        toast.success("Invite sent");
      },
      onError: (error: any) => {
        if (error.response.data) {
          toast.error(
            Array.isArray(error.response.data.email)
              ? error.response.data.email[0]
              : error.response.data.email
          );
        } else {
          toast.error("Cannot send an invite now, try again later.");
        }
      },
    }
  );

  const handleSendInviteEmail = (event: React.FormEvent<FormElements>) => {
    mutation.mutate({ email });
  };

  return (
    <div>
      <Typography.Title level={2}>Team Members</Typography.Title>
      <div className="flex flex-row space-x-10	">
        <div className="px-4 sm:px-6 lg:px-8 basis-7/12 border-2 border-solid rounded border-[#EAEAEB]">
          <div className="mt-8 flex flex-col">
            <div className="-my-2 -mx-4 overflow-x-auto sm:-mx-6 lg:-mx-8">
              <div className="inline-block min-w-full align-middle">
                <Table
                  className="min-w-full divide-y divide-gray-200"
                  pagination={false}
                  columns={
                    [
                      {
                        title: "Username",
                        dataIndex: "username",
                        key: "username",
                      },
                      {
                        title: "Email",
                        dataIndex: "email",
                        key: "email",
                      },
                      {
                        title: "Role",
                        dataIndex: "role",
                        key: "role",
                      },
                      {
                        title: "Status",
                        dataIndex: "status",
                        key: "status",
                        render: (status: string) => {
                          let color = status === "Active" ? "green" : "yellow";
                          return (
                            <Tag color={color} key={status}>
                              {status.toUpperCase()}
                            </Tag>
                          );
                        },
                      },
                      {
                        render(text, record) {
                          return (
                            <div className="flex flex-row space-x-2">
                              {/* <Button
                                type="primary"
                                onClick={() => {
                                  console.log(record);
                                }}
                              >
                                Edit
                              </Button> */}
                            </div>
                          );
                        },
                      },
                    ] as any
                  }
                  dataSource={organization?.users}
                />
              </div>
            </div>
          </div>
        </div>
        <div className="basis-5/12 justify-self-center	">
          <h2>Invite to Team</h2>
          <div className="w-96">
            <Form onFinish={handleSendInviteEmail} name="normal_login">
              <Form.Item>
                <label htmlFor="email">Email</label>
                <Input
                  type="text"
                  name="email"
                  value={email}
                  defaultValue="user123@email.com"
                  onChange={handleEmailChange}
                />
              </Form.Item>
              <Form.Item>
                <Button htmlType="submit">Send Invite</Button>
              </Form.Item>
            </Form>
          </div>
        </div>
      </div>

      {mutation.isLoading && <LoadingSpinner />}
    </div>
  );
};

export default TeamTab;
