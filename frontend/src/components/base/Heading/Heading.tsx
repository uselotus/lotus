import React from "react";
import { useLocation } from "react-router-dom";
import { RightOutlined } from "@ant-design/icons";
import Avatar from "../Avatar/Avatar";
import Badge from "../Badges/Badges";
import useGlobalStore from "../../../stores/useGlobalstore";
import useToggleSlideOver from "../../../stores/useToggleSlideOver";
interface HeadingProps {
  hasBackButton?: boolean;
  backButton?: React.ReactNode;
}

const Heading: React.FC<HeadingProps> = ({ hasBackButton, backButton }) => {
  const { current_user, environment } = useGlobalStore((state) => state.org);
  const { pathname } = useLocation();
  const setOpen = useToggleSlideOver((state) => state.setOpen);
  const currentPath = pathname.split("/")[1];
  const isPlansPage = currentPath === "plans";
  return (
    <div className="mt-16">
      <div className="flex cursor-pointer">
        <div className="bg-red">
          <input
            type="text"
            name="search"
            id="search"
            className={`block w-[120%] ml-[10px] rounded ${
              isPlansPage ? "bg-gold-50" : "bg-white"
            } p-4 outline-none sm:text-sm`}
            placeholder="Search..."
          />
        </div>
        <div className="flex items-center ml-[58%]">
          <div className="mr-10">
            <Badge
              onClick={setOpen}
              className={
                environment !== "production" ? "bg-blue-100 text-blue-800" : ""
              }
            >
              <Badge.Dot fill={environment !== "production" ? "#60A5FA" : ""} />
              <Badge.Content>
                <span className="flex gap-2 ml-2 justify-center items-center">
                  <span className="text-sm">{environment}</span>
                  <RightOutlined className="text-[10px]" />
                </span>
              </Badge.Content>
            </Badge>
          </div>
          <div
            className={`flex gap-4 items-center p-4 ${
              isPlansPage ? "hover:bg-gold-50" : "hover:bg-white"
            }`}
          >
            <Avatar className="w-16 h-16" />
            <span className="text-sm flex gap-2">
              {current_user.username}{" "}
              <svg
                className="-mr-1 ml-2 h-10 w-10"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="currentColor"
                aria-hidden="true"
              >
                <path
                  fill-rule="evenodd"
                  d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
                  clip-rule="evenodd"
                />
              </svg>
            </span>
          </div>
        </div>
      </div>
      {hasBackButton && backButton}
      <div className=" h-[1.5px] w-full bg-red" />
    </div>
  );
};

export default Heading;
