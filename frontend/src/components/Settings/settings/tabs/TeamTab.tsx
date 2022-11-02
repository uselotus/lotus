import React, { FC, useState } from "react";
import { useQuery, useMutation } from "react-query";
import { useNavigate } from "react-router-dom";
import { Divider, Typography, Row, Col, Input, Button, Form, Tag } from "antd";
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
    data: organization,
    isLoading,
    isError,
  } = useQuery(["organization"], () =>
    Organization.get().then((res) => {
      return res;
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
              <div className="inline-block min-w-full py-2 align-middle">
                <div className="overflow-hidden shadow-sm ring-1 ring-black ring-opacity-5">
                  <table className="min-w-full divide-y divide-gray-300">
                    <thead className="bg-gray-50">
                      <tr>
                        <th
                          scope="col"
                          className="py-3.5 pl-4 pr-3 text-left font-medium text-gray-900 sm:pl-6 lg:pl-8"
                        >
                          Username
                        </th>
                        <th
                          scope="col"
                          className="px-3 py-3.5 text-left font-medium text-gray-900"
                        >
                          Email
                        </th>
                        <th
                          scope="col"
                          className="px-3 py-3.5 text-left font-medium	text-gray-900"
                        >
                          Role
                        </th>
                        <th
                          scope="col"
                          className="px-3 py-3.5 text-left font-medium text-gray-900"
                        >
                          Status
                        </th>
                        <th
                          scope="col"
                          className="relative py-3.5 pl-3 pr-4 sm:pr-6 lg:pr-8"
                        >
                          <span className="sr-only">Edit</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 bg-white">
                      {organization?.team_members?.map((person, key) => (
                        <tr key={person.email}>
                          <td className="whitespace-nowrap py-4 pl-4 pr-3  text-gray-900 sm:pl-6 lg:pl-8">
                            {"N/A"}
                          </td>
                          <td className="whitespace-nowrap px-3 py-4 text-gray-500">
                            {person}
                          </td>
                          <td className="whitespace-nowrap px-3 py-4 text-gray-500">
                            {"Admin"}
                          </td>
                          <td className="whitespace-nowrap px-3 py-4 text-gray-500">
                            <Tag>{"Joined"}</Tag>
                          </td>
                          {/* <td className="relative whitespace-nowrap py-4 pl-3 pr-4 text-right  sm:pr-6 lg:pr-8">
                            <a
                              href="#"
                              className=" text-darkgold hover:text-black"
                            >
                              Edit
                              <span className="sr-only">, {person.name}</span>
                            </a>
                          </td> */}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
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
